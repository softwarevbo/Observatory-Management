import os
import hashlib
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from ..models import Release, ReleaseFile, ReleaseLog, ReleaseDeletionRequest
from files.models import ProjectFile

class ReleaseService:
    @staticmethod
    def calculate_hash(file_handle):
        """Calculates SHA-256 hash of a file."""
        sha256_hash = hashlib.sha256()
        # Handle both Django uploaded files and standard file handles
        if hasattr(file_handle, 'chunks'):
            for byte_block in file_handle.chunks():
                sha256_hash.update(byte_block)
        else:
            for byte_block in iter(lambda: file_handle.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    @staticmethod
    @transaction.atomic
    def create_release_snapshot(release, user, files_to_include=None):
        """
        Physically clones files from the project into the release storage.
        """
        if release.is_locked:
            return 0

        # Only snapshot once for project files (unless cleared)
        if release.release_files.filter(is_extra_asset=False).exists():
            return 0

        if files_to_include is not None:
            files_to_snapshot = files_to_include
        else:
            files_to_snapshot = ProjectFile.objects.filter(
                project=release.project,
                versions__isnull=True # Only latest versions
            )

        assets_created = 0
        for pf in files_to_snapshot:
            if pf.file and os.path.exists(pf.file.path):
                # 1. Calculate Hash
                with open(pf.file.path, "rb") as f:
                    file_hash = ReleaseService.calculate_hash(f)

                # 2. Create ReleaseFile record
                asset = ReleaseFile(
                    release=release,
                    project_file=pf,
                    original_name=pf.original_name,
                    relative_path=pf.get_project_relative_path(),
                    file_size=pf.file_size,
                    file_type=pf.file_type,
                    content_hash=file_hash,
                    version=pf.version,
                    is_extra_asset=False
                )
                
                # 3. Physical copy
                with open(pf.file.path, 'rb') as f:
                    asset.file.save(pf.original_name, ContentFile(f.read()), save=False)
                
                asset.save()
                assets_created += 1
        
        ReleaseLog.objects.create(
            release=release,
            user=user,
            action='snapshot_created',
            details=f"Snapshotted {assets_created} files from project."
        )
        return assets_created

    @staticmethod
    @transaction.atomic
    def publish_release(release, user):
        """
        Locks the release and marks it as published.
        """
        if release.is_locked:
            return
            
        # Ensure snapshot exists before publishing
        ReleaseService.create_release_snapshot(release, user)
        
        release.status = 'completed'
        release.published_at = timezone.now()
        release.published_by = user
        release.save()
        
        # Synchronize release assets to project resources
        ReleaseService.sync_release_to_project_resources(release, user)

        ReleaseLog.objects.create(
            release=release,
            user=user,
            action='published',
            details=f"Release published and locked."
        )

    @staticmethod
    def sync_release_to_project_resources(release, user):
        """
        Creates ProjectFile records for each ReleaseFile so they appear in the project resources.
        Also generates a complete release bundle (ZIP).
        """
        import io
        import zipfile
        from files.models import FileCategory, ProjectFile
        from django.core.files.base import ContentFile

        # 1. Get or create "Releases" root category
        releases_root, _ = FileCategory.objects.get_or_create(
            name="Releases",
            project=release.project,
            parent=None,
            defaults={'created_by': user}
        )

        # 2. Get or create category for THIS release
        release_name = release.version or release.tag_name or release.name
        rel_cat, _ = FileCategory.objects.get_or_create(
            name=release_name,
            project=release.project,
            parent=releases_root,
            defaults={'created_by': user}
        )

        # 3. For each ReleaseFile, create a ProjectFile record
        synced_count = 0
        all_rf = release.release_files.all()
        for rf in all_rf:
            if not rf.file:
                continue
            
            # Resolve sub-folder path
            target_cat = rel_cat
            if rf.relative_path:
                parts = os.path.normpath(rf.relative_path).split(os.sep)
                # Remove file name from parts, keep directories
                dirs = parts[:-1]
                for d in dirs:
                    target_cat, _ = FileCategory.objects.get_or_create(
                        name=d,
                        project=release.project,
                        parent=target_cat,
                        defaults={'created_by': user}
                    )

            # Check if already synced (idempotency)
            if ProjectFile.objects.filter(
                project=release.project,
                category=target_cat,
                original_name=os.path.basename(rf.original_name),
                release=release
            ).exists():
                continue

            # Create new ProjectFile
            pf = ProjectFile(
                project=release.project,
                release=release,
                category=target_cat,
                original_name=os.path.basename(rf.original_name),
                file_size=rf.file_size,
                file_type=rf.file_type,
                uploaded_by=user,
                is_public=True,
                description=f"Immutable snapshot from release {release_name}"
            )

            # Copy file content
            try:
                with rf.file.open('rb') as f:
                    pf.file.save(os.path.basename(rf.original_name), ContentFile(f.read()), save=False)
                pf.save()
                synced_count += 1
            except Exception:
                continue
        
        # 4. Generate and save a Release Bundle (ZIP)
        if all_rf.exists():
            bundle_name = f"Release_{release_name}_Complete.zip".replace(" ", "_")
            if not ProjectFile.objects.filter(project=release.project, category=rel_cat, original_name=bundle_name).exists():
                try:
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        for rf in all_rf:
                            if rf.file and os.path.exists(rf.file.path):
                                zip_file.write(rf.file.path, arcname=rf.get_project_relative_path())
                    
                    pf_bundle = ProjectFile(
                        project=release.project,
                        release=release,
                        category=rel_cat,
                        original_name=bundle_name,
                        uploaded_by=user,
                        is_public=True,
                        description=f"Complete release bundle for {release_name}"
                    )
                    pf_bundle.file.save(bundle_name, ContentFile(zip_buffer.getvalue()), save=False)
                    pf_bundle.save()
                    synced_count += 1
                except Exception:
                    pass
        
        return synced_count

    @staticmethod
    def add_asset_to_release(release, file_obj, user):
        """
        Adds an extra asset (binary, pdf, etc) to a draft release.
        """
        if release.is_locked:
            raise Exception("Cannot add assets to a locked release.")
            
        file_hash = ReleaseService.calculate_hash(file_obj)
            
        asset = ReleaseFile(
            release=release,
            original_name=file_obj.name,
            file_size=file_obj.size,
            file_type=file_obj.name.split('.')[-1] if '.' in file_obj.name else 'bin',
            content_hash=file_hash,
            is_extra_asset=True
        )
        asset.file.save(file_obj.name, file_obj, save=True)
        
        ReleaseLog.objects.create(
            release=release,
            user=user,
            action='asset_uploaded',
            details=f"Uploaded extra asset: {file_obj.name}"
        )
        return asset

    @staticmethod
    def compare_releases(release_a, release_b):
        """
        Compares two releases and returns added, removed, and modified files.
        """
        assets_a = {a.original_name: a for a in release_a.release_files.all()}
        assets_b = {b.original_name: b for b in release_b.release_files.all()}

        added = []
        removed = []
        modified = []
        unchanged = []

        for name, asset_b in assets_b.items():
            if name not in assets_a:
                added.append(asset_b)
            else:
                asset_a = assets_a[name]
                if asset_a.content_hash != asset_b.content_hash:
                    modified.append({'name': name, 'old': asset_a, 'new': asset_b})
                else:
                    unchanged.append(asset_b)

        for name, asset_a in assets_a.items():
            if name not in assets_b:
                removed.append(asset_a)

        return {
            'added': added,
            'removed': removed,
            'modified': modified,
            'unchanged': unchanged
        }

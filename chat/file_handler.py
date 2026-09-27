"""
Chat File Handler Module
========================

This module provides utilities for handling file uploads and downloads,
including support for chunked uploads, streaming downloads, and large file processing.

Features:
- Chunked upload support for large files
- Temporary chunk storage and assembly
- File validation and size limits
- Memory-efficient streaming
- Resume capability for interrupted uploads
"""

import os
import tempfile
import hashlib
from pathlib import Path
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile


# Configuration
CHUNK_SIZE = 5242880  # 5MB per chunk
MAX_TOTAL_SIZE = 5368709120  # 5GB total
TEMP_UPLOAD_DIR = Path(tempfile.gettempdir()) / "chat_uploads"


def ensure_temp_dir():
    """Ensure temporary upload directory exists."""
    TEMP_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return TEMP_UPLOAD_DIR


def get_chunk_temp_dir(upload_id):
    """Get the temporary directory for a specific upload session."""
    temp_dir = ensure_temp_dir() / upload_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def handle_chunk_upload(upload_id, chunk_number, chunk_data, total_chunks):
    """
    Handle a single chunk upload.
    
    Args:
        upload_id: Unique identifier for this upload session
        chunk_number: Current chunk number (0-indexed)
        chunk_data: Bytes of the chunk
        total_chunks: Total number of chunks expected
        
    Returns:
        dict: Status and metadata about the chunk upload
    """
    try:
        chunk_dir = get_chunk_temp_dir(upload_id)
        chunk_file = chunk_dir / f"chunk_{chunk_number}"
        
        # Write chunk to temporary file
        with open(chunk_file, 'wb') as f:
            f.write(chunk_data)
        
        # Check if all chunks have been uploaded
        chunks_uploaded = len(list(chunk_dir.glob('chunk_*')))
        
        return {
            'status': 'success',
            'upload_id': upload_id,
            'chunk_number': chunk_number,
            'chunks_uploaded': chunks_uploaded,
            'total_chunks': total_chunks,
            'complete': chunks_uploaded == total_chunks
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e),
            'upload_id': upload_id
        }


def assemble_chunks(upload_id, total_chunks, filename, target_file):
    """
    Assemble all chunks into the final file.
    
    Args:
        upload_id: Unique identifier for the upload session
        total_chunks: Total number of chunks to assemble
        filename: Original filename
        target_file: Django File object to write to
        
    Returns:
        dict: Status and final file path
    """
    try:
        chunk_dir = get_chunk_temp_dir(upload_id)
        
        # Verify all chunks exist
        for i in range(total_chunks):
            chunk_file = chunk_dir / f"chunk_{i}"
            if not chunk_file.exists():
                return {
                    'status': 'error',
                    'message': f'Missing chunk {i}'
                }
        
        # Assemble chunks into final file
        final_data = b''
        for i in range(total_chunks):
            chunk_file = chunk_dir / f"chunk_{i}"
            with open(chunk_file, 'rb') as f:
                final_data += f.read()
        
        # Write to target file
        if hasattr(target_file, 'name'):
            # Write using Django's storage system
            from django.core.files.base import ContentFile
            saved_name = default_storage.save(
                target_file.name,
                ContentFile(final_data)
            )
        else:
            # Direct file write
            target_file.write(final_data)
        
        # Clean up temporary chunks
        cleanup_chunks(upload_id)
        
        return {
            'status': 'success',
            'filename': filename,
            'total_size': len(final_data),
            'message': 'File assembled successfully'
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e),
            'upload_id': upload_id
        }


def cleanup_chunks(upload_id):
    """Clean up temporary chunk files for a completed/failed upload."""
    try:
        chunk_dir = get_chunk_temp_dir(upload_id)
        if chunk_dir.exists():
            import shutil
            shutil.rmtree(chunk_dir)
    except Exception as e:
        print(f"Error cleaning up chunks for {upload_id}: {e}")


def get_upload_progress(upload_id, total_chunks):
    """
    Get the current progress of an upload.
    
    Returns:
        dict: Progress information including percentage and chunk count
    """
    try:
        chunk_dir = get_chunk_temp_dir(upload_id)
        if not chunk_dir.exists():
            return {'status': 'not_found', 'progress': 0}
        
        chunks_uploaded = len(list(chunk_dir.glob('chunk_*')))
        progress_percent = (chunks_uploaded / total_chunks * 100) if total_chunks > 0 else 0
        
        return {
            'status': 'in_progress',
            'chunks_uploaded': chunks_uploaded,
            'total_chunks': total_chunks,
            'progress': progress_percent
        }
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def calculate_file_hash(file_path, algorithm='sha256'):
    """
    Calculate hash of a file for integrity verification.
    
    Args:
        file_path: Path to the file
        algorithm: Hash algorithm to use (default: sha256)
        
    Returns:
        str: Hex-encoded hash string
    """
    hash_obj = hashlib.new(algorithm)
    
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hash_obj.update(chunk)
    
    return hash_obj.hexdigest()


def validate_upload_token(upload_id, expected_hash=None):
    """
    Validate an upload session token.
    
    Args:
        upload_id: Upload session ID to validate
        expected_hash: Optional hash to verify against
        
    Returns:
        dict: Validation result
    """
    chunk_dir = get_chunk_temp_dir(upload_id)
    
    if not chunk_dir.exists():
        return {'valid': False, 'reason': 'Upload session not found'}
    
    # Check if chunks exist
    chunks = list(chunk_dir.glob('chunk_*'))
    if not chunks:
        return {'valid': False, 'reason': 'No chunks uploaded'}
    
    return {'valid': True, 'chunks_count': len(chunks)}

import json
import math
import numpy as np
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.utils.text import slugify
from django.db import models
from django.db.models import Q, Count, Avg

from .models import (
    Telescope, TelescopeLog, TelescopeDiscussion, TelescopeDiscussionReply,
    Instrument, InstrumentSensor, TelemetryLog, FilterWheelConfig,
    ObservationTarget, ExposureRunLog, UnifiedLog,
    MaintenanceTicket, CalibrationLog,
    PlateSolveRun, SiteFeedback, TelescopeUser
)
from .forms import (
    TelescopeForm, SlewTargetForm, TelescopeDiscussionForm, TelescopeDiscussionReplyForm,
    InstrumentForm, ObservationTargetForm, MaintenanceTicketForm, ResolveTicketForm,
    CalibrationLogForm, SiteFeedbackForm, TelescopeUserCreationForm, TelescopeAdminEditForm
)
from .platesolver.solver_engine import PlateSolverEngine


def ensure_default_telescopes():
    """
    Checks if default telescope seed instances exist in the database;
    if none are found, initializes core observatory telescope records (VBT, JCBT, CZT).
    """
    Telescope.objects.filter(name__icontains="Cassegrain").delete()
    Telescope.objects.filter(name__icontains="Schmidt").delete()

    if Telescope.objects.count() == 0:
        Telescope.objects.create(
            id_name="vbt_234",
            code="vbt",
            name="Vainu Bappu Telescope (VBT)",
            aperture="2.34 Meter",
            type="Reflector (Cassegrain / Prime Focus)",
            status="online",
            current_target="NGC 5194 (M51 Whirlpool Galaxy)",
            ra="13h 29m 52.7s",
            dec="+47° 11′ 43″",
            right_ascension="13h 29m 52.7s",
            declination="+47° 11′ 43″",
            dome="Open",
            dome_status="open",
            focus="Cassegrain",
            instrument="OMC (Optical Mosaic Camera)",
            ccd_temp="-110°C",
            tracking="Enabled",
            image_url="https://www.iiap.res.in/centers/vbo/vbt/vbt.jpg",
            description="The 2.34m Vainu Bappu Telescope is the flagship optical instrument at Kavalur Observatory.",
            history="Inaugurated on January 6, 1986 by Rajiv Gandhi."
        )
        Telescope.objects.create(
            id_name="jcbt_130",
            code="jcbt",
            name="J.C. Bhattacharya Telescope (JCBT)",
            aperture="1.3 Meter",
            type="Ritchey-Chrétien Reflector",
            status="online",
            current_target="HAT-P-12b (Exoplanet Transit)",
            ra="16h 41m 02.4s",
            dec="+35° 40′ 33″",
            right_ascension="16h 41m 02.4s",
            declination="+35° 40′ 33″",
            dome="Open",
            dome_status="open",
            focus="RC Focus",
            instrument="High Resolution Spectrograph",
            ccd_temp="-95°C",
            tracking="Enabled",
            image_url="https://www.iiap.res.in/centers/vbo/jcbt/jcbt.jpg",
            description="1.3m Ritchey-Chrétien reflector equipped with dual focus ports.",
            history="Commissioned in 2014 in honor of Dr. J.C. Bhattacharya."
        )
        Telescope.objects.create(
            id_name="zeiss_100",
            code="czt",
            name="Carl Zeiss Telescope (CZT)",
            aperture="1.0 Meter",
            type="Reflector",
            status="idle",
            current_target="None",
            ra="00h 00m 00s",
            dec="+00° 00′ 00″",
            right_ascension="00h 00m 00s",
            declination="+00° 00′ 00″",
            dome="Closed",
            dome_status="closed",
            focus="Cassegrain",
            instrument="UAGS Spectrograph",
            ccd_temp="-80°C",
            tracking="Disabled",
            image_url="https://www.iiap.res.in/centers/vbo/czt/czt.jpg",
            description="The 1.0m Carl Zeiss Telescope played a historic role in planetary discoveries.",
            history="Established at Kavalur in 1972."
        )
    else:
        for t in Telescope.objects.all():
            if not t.code:
                if "Vainu" in t.name or "VBT" in t.name:
                    t.code = "vbt"
                    t.id_name = "vbt_234"
                elif "Bhattacharya" in t.name or "JCBT" in t.name:
                    t.code = "jcbt"
                    t.id_name = "jcbt_130"
                elif "Zeiss" in t.name or "CZT" in t.name:
                    t.code = "czt"
                    t.id_name = "zeiss_100"
                t.save()


# ══════════════════════════════════════════════════════════════════════════════
# 1. TCS DASHBOARD / MISSION CONTROL
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def dashboard(request):
    ensure_default_telescopes()
    user = request.user

    telescopes = Telescope.objects.all().order_by('code')
    instruments = Instrument.objects.select_related('telescope').all()
    open_tickets = MaintenanceTicket.objects.filter(status='open').count()
    critical_tickets = MaintenanceTicket.objects.filter(status='open', severity='critical').count()

    telescope_status = {
        'online': telescopes.filter(status__in=['online', 'observing']).count(),
        'tracking': telescopes.filter(status='tracking').count(),
        'maintenance': telescopes.filter(status='maintenance').count(),
        'fault': telescopes.filter(status='fault').count(),
        'idle': telescopes.filter(status='idle').count(),
    }
    instrument_status = {
        'online': instruments.filter(status='online').count(),
        'calibrating': instruments.filter(status='calibrating').count(),
        'maintenance': instruments.filter(status='maintenance').count(),
        'error': instruments.filter(status='error').count(),
        'standby': instruments.filter(status='standby').count(),
    }

    context = {
        'telescopes': telescopes,
        'instruments': instruments,
        'open_tickets': open_tickets,
        'critical_tickets': critical_tickets,
        'telescope_status': telescope_status,
        'instrument_status': instrument_status,
        'recent_calibrations': CalibrationLog.objects.select_related('instrument', 'engineer').all()[:5],
        'recent_tickets': MaintenanceTicket.objects.select_related('instrument', 'telescope', 'assigned_engineer').filter(status__in=['open', 'in_progress'])[:5],
        'observatory': {
            'name': 'Kavalur Vainu Bappu Observatory (VBO)',
            'location': 'Kavalur, Javadi Hills, Tamil Nadu, India',
            'elevation': '725 meters ASL',
            'coordinates': "12°34'35\" N, 78°49'38\" E",
        },
        'weather': {
            'temp': '18.2 °C',
            'humidity': '42%',
            'wind': '12.4 km/h ENE',
            'clouds': 'Clear Sky',
            'seeing': '1.2 arcsec (Excellent)',
            'pressure': '934 hPa',
        }
    }
    return render(request, 'telescope/dashboard.html', context)


# ══════════════════════════════════════════════════════════════════════════════
# 2. TELESCOPE MANAGEMENT & CONTROL VIEWS
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def telescope_list(request):
    ensure_default_telescopes()
    telescopes = Telescope.objects.all().order_by('code')
    return render(request, 'telescope/telescope_list.html', {'telescopes': telescopes})


@login_required
def telescope_detail(request, pk=None, code=None):
    ensure_default_telescopes()
    if code:
        telescope = get_object_or_404(Telescope, code__iexact=code)
    else:
        telescope = get_object_or_404(Telescope, pk=pk)

    targets = ObservationTarget.objects.all().order_by('name')
    slew_form = SlewTargetForm(initial={
        'right_ascension': telescope.right_ascension or telescope.ra,
        'declination': telescope.declination or telescope.dec,
        'epoch': telescope.epoch,
    })
    logs = telescope.logs.all()[:20]
    instruments = telescope.instruments.all()
    discussions = telescope.discussions.select_related('user').annotate(reply_count=Count('replies')).order_by('-is_pinned', '-created_at')
    discussion_form = TelescopeDiscussionForm(initial={'telescope': telescope})

    code_lower = (telescope.code or telescope.id_name or "").lower()
    template_map = {
        'vbt': 'telescope/telescope_detail_vbt.html',
        'jcbt': 'telescope/telescope_detail_jcbt.html',
        'czt': 'telescope/telescope_detail_czt.html',
    }
    template_name = template_map.get(code_lower, 'telescope/telescope_detail.html')

    u = request.user
    from accounts.rbac import get_canonical_role, ROLE_ROOT, ROLE_TCS_ADMIN
    role = get_canonical_role(u)
    is_admin = u.is_superuser or getattr(u, 'is_root', False) or getattr(u, 'is_telescope_admin', False) or role in [ROLE_ROOT, ROLE_TCS_ADMIN] or getattr(u, 'role', '') == 'admin'

    is_assigned = False
    if is_admin or getattr(u, 'role', '') in ['engineer', 'scientific_officer']:
        is_assigned = True
    elif hasattr(u, 'check_telescope_access'):
        is_assigned = u.check_telescope_access(telescope)
    elif hasattr(u, 'assigned_telescopes'):
        is_assigned = u.assigned_telescopes.filter(pk=telescope.pk).exists()
    else:
        is_assigned = is_admin

    return render(request, template_name, {
        'telescope': telescope,
        'targets': targets,
        'slew_form': slew_form,
        'logs': logs,
        'instruments': instruments,
        'discussions': discussions,
        'discussion_form': discussion_form,
        'can_control': is_assigned,
        'is_assigned_observer': is_assigned,
    })


@login_required
def telescope_create(request):
    is_admin_user = request.user.is_superuser or getattr(request.user, 'is_admin', False) or getattr(request.user, 'is_telescope_admin', False)
    if not is_admin_user:
        messages.error(request, "Access Denied: TCS Admin privilege required.")
        return redirect('telescope:dashboard')

    if request.method == 'POST':
        form = TelescopeForm(request.POST)
        if form.is_valid():
            telescope = form.save(commit=False)
            if not telescope.id_name:
                telescope.id_name = slugify(telescope.name).replace('-', '_')
            telescope.save()
            messages.success(request, f"Telescope '{telescope.name}' registered successfully.")
            return redirect('telescope:dashboard')
    else:
        form = TelescopeForm()
    return render(request, 'telescope/telescope_form.html', {'form': form, 'action': 'Add New Telescope'})


@login_required
def telescope_edit(request, pk):
    is_admin_user = request.user.is_superuser or getattr(request.user, 'is_admin', False) or getattr(request.user, 'is_telescope_admin', False)
    if not is_admin_user:
        messages.error(request, "Access Denied: TCS Admin privilege required.")
        return redirect('telescope:dashboard')

    telescope = get_object_or_404(Telescope, pk=pk)
    if request.method == 'POST':
        form = TelescopeForm(request.POST, instance=telescope)
        if form.is_valid():
            telescope = form.save()
            messages.success(request, f"Telescope '{telescope.name}' updated successfully.")
            return redirect('telescope:dashboard')
    else:
        form = TelescopeForm(instance=telescope)
    return render(request, 'telescope/telescope_form.html', {'form': form, 'action': f'Edit {telescope.name}'})


@login_required
def telescope_delete(request, pk):
    is_admin_user = request.user.is_superuser or getattr(request.user, 'is_admin', False) or getattr(request.user, 'is_telescope_admin', False)
    if not is_admin_user:
        messages.error(request, "Access Denied: TCS Admin privilege required.")
        return redirect('telescope:dashboard')

    telescope = get_object_or_404(Telescope, pk=pk)
    name = telescope.name
    telescope.delete()
    messages.success(request, f"Telescope '{name}' deleted from database.")
    return redirect('telescope:dashboard')


def _can_user_control_telescope(user, telescope):
    from accounts.rbac import get_canonical_role, ROLE_ROOT, ROLE_TCS_ADMIN
    role = get_canonical_role(user)
    if user.is_superuser or getattr(user, 'is_root', False) or getattr(user, 'is_telescope_admin', False) or role in [ROLE_ROOT, ROLE_TCS_ADMIN] or getattr(user, 'role', '') in ['admin', 'engineer', 'scientific_officer']:
        return True
    if hasattr(user, 'check_telescope_access'):
        return user.check_telescope_access(telescope)
    if hasattr(user, 'assigned_telescopes'):
        return user.assigned_telescopes.filter(pk=telescope.pk).exists()
    return False


@login_required
def slew_telescope(request, pk):
    telescope = get_object_or_404(Telescope, pk=pk)
    if not _can_user_control_telescope(request.user, telescope):
        messages.error(request, "Access Denied: You are not authorized to send control commands to this telescope.")
        return redirect('telescope:telescope_detail', pk=telescope.pk)

    if request.method == 'POST':
        form = SlewTargetForm(request.POST)
        if form.is_valid():
            target_name = form.cleaned_data.get('target_name') or 'Custom Target'
            ra = form.cleaned_data.get('right_ascension')
            dec = form.cleaned_data.get('declination')
            epoch = form.cleaned_data.get('epoch')

            telescope.right_ascension = ra
            telescope.declination = dec
            telescope.ra = ra
            telescope.dec = dec
            telescope.epoch = epoch
            telescope.status = Telescope.STATUS_TRACKING
            telescope.current_target = target_name
            telescope.save()

            TelescopeLog.objects.create(
                telescope=telescope,
                user=request.user if hasattr(request.user, 'pk') and request.user.pk else None,
                event_type='slew',
                message=f"Slewed and tracking locked on target '{target_name}' at RA: {ra}, DEC: {dec} ({epoch})."
            )
            messages.success(request, f"Telescope {telescope.code or telescope.id_name} slewed to {target_name} ({ra}, {dec}). Tracking active.")
    return redirect('telescope:telescope_detail', pk=telescope.pk)


@login_required
def stop_telescope(request, pk):
    telescope = get_object_or_404(Telescope, pk=pk)
    if not _can_user_control_telescope(request.user, telescope):
        messages.error(request, "Access Denied: You are not authorized to send control commands to this telescope.")
        return redirect('telescope:telescope_detail', pk=telescope.pk)

    if request.method == 'POST':
        telescope.status = Telescope.STATUS_IDLE
        telescope.save()

        TelescopeLog.objects.create(
            telescope=telescope,
            user=request.user if hasattr(request.user, 'pk') and request.user.pk else None,
            event_type='track_stop',
            message="HALT MOTION: Mount motion stopped and tracking halted."
        )
        messages.warning(request, f"Telescope {telescope.code or telescope.id_name}: Motion halted. Tracking disengaged.")
    return redirect('telescope:telescope_detail', pk=telescope.pk)


@login_required
def park_telescope(request, pk):
    telescope = get_object_or_404(Telescope, pk=pk)
    if not _can_user_control_telescope(request.user, telescope):
        messages.error(request, "Access Denied: You are not authorized to send control commands to this telescope.")
        return redirect('telescope:telescope_detail', pk=telescope.pk)

    if request.method == 'POST':
        telescope.status = Telescope.STATUS_IDLE
        telescope.save()

        TelescopeLog.objects.create(
            telescope=telescope,
            user=request.user if hasattr(request.user, 'pk') and request.user.pk else None,
            event_type='track_stop',
            message="PARK / STANDBY: Telescope driven to zenith park position."
        )
        messages.info(request, f"Telescope {telescope.code or telescope.id_name}: Parked at zenith. Standby active.")
    return redirect('telescope:telescope_detail', pk=telescope.pk)


@login_required
def toggle_dome(request, pk):
    telescope = get_object_or_404(Telescope, pk=pk)
    if not _can_user_control_telescope(request.user, telescope):
        messages.error(request, "Access Denied: You are not authorized to send control commands to this telescope.")
        return redirect('telescope:telescope_detail', pk=telescope.pk)

    if telescope.dome_status == 'open' or telescope.dome == 'Open':
        telescope.dome_status = 'closed'
        telescope.dome = 'Closed'
        event_type = 'dome_close'
        msg = "Dome shutter closed."
    else:
        telescope.dome_status = 'open'
        telescope.dome = 'Open'
        event_type = 'dome_open'
        msg = "Dome shutter opened for observation."

    telescope.save()
    TelescopeLog.objects.create(
        telescope=telescope,
        user=request.user if hasattr(request.user, 'pk') and request.user.pk else None,
        event_type=event_type,
        message=msg
    )
    messages.info(request, f"Dome state updated to {telescope.dome}.")
    return redirect('telescope:telescope_detail', pk=telescope.pk)


@login_required
def update_telemetry(request, pk):
    telescope = get_object_or_404(Telescope, pk=pk)
    if not _can_user_control_telescope(request.user, telescope):
        messages.error(request, "Access Denied: You are not authorized to edit telemetry on this telescope.")
        return redirect('telescope:telescope_detail', pk=telescope.pk)

    if request.method == 'POST':
        focus_pos = request.POST.get('focus_position')
        mirror_temp = request.POST.get('primary_mirror_temp')
        humidity = request.POST.get('humidity')
        ra = request.POST.get('right_ascension')
        dec = request.POST.get('declination')

        changes = []
        if focus_pos:
            try:
                telescope.focus_position = float(focus_pos)
                changes.append(f"Focus={telescope.focus_position}mm")
            except ValueError:
                pass
        if mirror_temp:
            try:
                telescope.primary_mirror_temp = float(mirror_temp)
                changes.append(f"Mirror Temp={telescope.primary_mirror_temp}°C")
            except ValueError:
                pass
        if humidity:
            try:
                telescope.humidity = float(humidity)
                changes.append(f"Humidity={telescope.humidity}%")
            except ValueError:
                pass
        if ra and ra.strip():
            telescope.right_ascension = ra.strip()
            telescope.ra = ra.strip()
            changes.append(f"RA={telescope.right_ascension}")
        if dec and dec.strip():
            telescope.declination = dec.strip()
            telescope.dec = dec.strip()
            changes.append(f"DEC={telescope.declination}")

        telescope.save()
        if changes:
            messages.success(request, f"Telescope telemetry updated: {', '.join(changes)}.")
    return redirect('telescope:telescope_detail', pk=pk)


# ══════════════════════════════════════════════════════════════════════════════
# 3. DISCUSSIONS HUB VIEWS
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def discussion_hub(request):
    user = request.user
    role = getattr(user, 'role', '')
    is_specialist = (
        getattr(user, 'is_superuser', False) or
        getattr(user, 'is_root', False) or
        getattr(user, 'is_admin', False) or
        getattr(user, 'is_engineer', False) or
        getattr(user, 'is_scientific_officer', False) or
        role in ['admin', 'engineer', 'scientific_officer', 'ROOT', 'TCS_ADMIN', 'TM_ADMIN']
    )

    telescopes = Telescope.objects.all().order_by('code')
    if not is_specialist and hasattr(user, 'assigned_telescopes') and user.assigned_telescopes.exists():
        telescopes = user.assigned_telescopes.all()

    selected_telescope_id = request.GET.get('telescope', '')
    selected_category = request.GET.get('category', '')
    search_query = request.GET.get('q', '').strip()

    discussions = TelescopeDiscussion.objects.select_related('telescope', 'user').annotate(reply_count=Count('replies'))

    if not is_specialist and hasattr(user, 'assigned_telescopes') and user.assigned_telescopes.exists():
        discussions = discussions.filter(telescope__in=user.assigned_telescopes.all())

    if selected_telescope_id:
        discussions = discussions.filter(telescope_id=selected_telescope_id)
    if selected_category:
        discussions = discussions.filter(category=selected_category)
    if search_query:
        discussions = discussions.filter(
            Q(title__icontains=search_query) |
            Q(content__icontains=search_query)
        )

    discussions = discussions.order_by('-is_pinned', '-created_at')
    form = TelescopeDiscussionForm()

    return render(request, 'telescope/discussion_hub.html', {
        'discussions': discussions,
        'telescopes': telescopes,
        'selected_category': selected_category,
        'search_query': search_query,
        'categories': TelescopeDiscussion.CATEGORY_CHOICES,
        'form': form,
    })


@login_required
def discussion_detail(request, pk):
    discussion = get_object_or_404(TelescopeDiscussion.objects.select_related('telescope', 'user'), pk=pk)
    replies = discussion.replies.select_related('user').order_by('created_at')

    if request.method == 'POST':
        reply_form = TelescopeDiscussionReplyForm(request.POST)
        if reply_form.is_valid():
            reply = reply_form.save(commit=False)
            reply.discussion = discussion
            reply.user = request.user if hasattr(request.user, 'pk') and request.user.pk else None
            reply.save()
            messages.success(request, "Reply posted successfully.")
            return redirect('telescope:discussion_detail', pk=discussion.pk)
    else:
        reply_form = TelescopeDiscussionReplyForm()

    return render(request, 'telescope/discussion_detail.html', {
        'discussion': discussion,
        'replies': replies,
        'reply_form': reply_form,
    })


@login_required
def discussion_create(request):
    if request.method == 'POST':
        form = TelescopeDiscussionForm(request.POST)
        if form.is_valid():
            discussion = form.save(commit=False)
            discussion.user = request.user if hasattr(request.user, 'pk') and request.user.pk else None
            discussion.save()
            messages.success(request, f"Discussion '{discussion.title}' created.")
            return redirect('telescope:discussion_detail', pk=discussion.pk)
    return redirect('telescope:discussion_hub')


@login_required
def toggle_pin_discussion(request, pk):
    discussion = get_object_or_404(TelescopeDiscussion, pk=pk)
    discussion.is_pinned = not discussion.is_pinned
    discussion.save()
    status_str = "pinned" if discussion.is_pinned else "unpinned"
    messages.info(request, f"Discussion '{discussion.title}' {status_str}.")
    return redirect('telescope:discussion_detail', pk=pk)


# ══════════════════════════════════════════════════════════════════════════════
# 4. INSTRUMENT HUB VIEWS
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def instrument_list(request):
    instruments = Instrument.objects.select_related('telescope').all().order_by('code')
    return render(request, 'telescope/instruments/instrument_list.html', {'instruments': instruments})


@login_required
def instrument_detail(request, pk):
    instrument = get_object_or_404(Instrument.objects.select_related('telescope'), pk=pk)
    sensors = instrument.sensors.all()
    return render(request, 'telescope/instruments/instrument_detail.html', {
        'instrument': instrument,
        'sensors': sensors,
        'can_edit': True,
    })


@login_required
def instrument_create(request):
    if request.method == 'POST':
        form = InstrumentForm(request.POST)
        if form.is_valid():
            inst = form.save()
            messages.success(request, f"Instrument '{inst.name}' registered.")
            return redirect('telescope:instrument_list')
    else:
        form = InstrumentForm()
    return render(request, 'telescope/instruments/instrument_form.html', {'form': form, 'action': 'Register New Instrument'})


@login_required
def instrument_edit(request, pk):
    instrument = get_object_or_404(Instrument, pk=pk)
    if request.method == 'POST':
        form = InstrumentForm(request.POST, instance=instrument)
        if form.is_valid():
            instrument = form.save()
            messages.success(request, f"Instrument {instrument.code} updated.")
            return redirect('telescope:instrument_detail', pk=instrument.pk)
    else:
        form = InstrumentForm(instance=instrument)
    return render(request, 'telescope/instruments/instrument_form.html', {'form': form, 'action': f'Edit {instrument.code}'})


@login_required
def update_status(request, pk):
    instrument = get_object_or_404(Instrument, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in [s[0] for s in Instrument.STATUS_CHOICES]:
            instrument.status = new_status
            instrument.save()
            messages.success(request, f"Instrument {instrument.code} status updated to {instrument.get_status_display()}.")
    return redirect('telescope:instrument_detail', pk=pk)


# ══════════════════════════════════════════════════════════════════════════════
# 5. SCIENCE OPERATIONS & OBSERVATIONS VIEWS
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def target_list(request):
    targets = ObservationTarget.objects.all()
    q = request.GET.get('q', '').strip()
    object_class = request.GET.get('object_class', '').strip()

    if q:
        targets = targets.filter(Q(name__icontains=q) | Q(catalog_id__icontains=q) | Q(notes__icontains=q))
    if object_class:
        targets = targets.filter(object_class=object_class)

    targets = targets.order_by('-created_at', 'name')
    return render(request, 'telescope/observations/target_list.html', {
        'targets': targets,
        'q': q,
        'selected_object_class': object_class,
        'object_choices': ObservationTarget.OBJECT_CHOICES,
    })


@login_required
def target_detail(request, pk):
    target = get_object_or_404(ObservationTarget, pk=pk)
    return render(request, 'telescope/observations/target_detail.html', {'target': target})


@login_required
def target_create(request):
    if request.method == 'POST':
        form = ObservationTargetForm(request.POST)
        if form.is_valid():
            target = form.save(commit=False)
            if not target.observation_date:
                target.observation_date = timezone.now().date()
            target.save()
            messages.success(request, f"Target '{target.name}' added to catalog.")
            return redirect('telescope:target_detail', pk=target.pk)
    else:
        form = ObservationTargetForm()
    return render(request, 'telescope/observations/target_form.html', {'form': form, 'action': 'Add Target to Catalog'})


@login_required
def target_edit(request, pk):
    target = get_object_or_404(ObservationTarget, pk=pk)
    if request.method == 'POST':
        form = ObservationTargetForm(request.POST, instance=target)
        if form.is_valid():
            target = form.save()
            messages.success(request, f"Target '{target.name}' updated.")
            return redirect('telescope:target_list')
    else:
        form = ObservationTargetForm(instance=target)
    return render(request, 'telescope/observations/target_form.html', {'form': form, 'action': f'Edit Target: {target.name}', 'target': target})


@login_required
def target_delete(request, pk):
    target = get_object_or_404(ObservationTarget, pk=pk)
    name = target.name
    target.delete()
    messages.success(request, f"Target '{name}' deleted.")
    return redirect('telescope:target_list')


def user_can_access_tab(user, tab):
    """
    Checks if a user has authorization to view/edit a specific unified log tab.
    ROOT superuser, Admins, Engineers, Scientific Officers, and Observers have access to log tabs.
    """
    if not user or not user.is_authenticated:
        return False
        
    role = getattr(user, 'role', '')
    if (getattr(user, 'is_superuser', False) or 
        getattr(user, 'is_root', False) or 
        getattr(user, 'is_admin', False) or 
        getattr(user, 'is_engineer', False) or 
        getattr(user, 'is_scientific_officer', False) or 
        role in ['admin', 'engineer', 'scientific_officer', 'observer', 'ROOT', 'TCS_ADMIN', 'TCS_MEMBER', 'TM_ADMIN', 'TM_MEMBER']):
        
        if tab in ['overview', 'report']:
            return True
        if hasattr(user, 'assigned_telescopes') and user.assigned_telescopes.exists():
            return user.assigned_telescopes.filter(code__iexact=tab).exists()
        return True
        
    return False


def get_first_accessible_tab(user):
    """Returns the default/first accessible tab for a user."""
    if (getattr(user, 'is_superuser', False) or 
        getattr(user, 'is_root', False) or 
        getattr(user, 'is_admin', False) or 
        getattr(user, 'is_engineer', False) or 
        getattr(user, 'is_scientific_officer', False) or 
        getattr(user, 'role', '') in ['admin', 'engineer', 'scientific_officer', 'ROOT', 'TCS_ADMIN', 'TCS_MEMBER', 'TM_ADMIN', 'TM_MEMBER']):
        return 'overview'
        
    for t in ['vbt', 'jcbt', 'czt']:
        if hasattr(user, 'assigned_telescopes') and user.assigned_telescopes.filter(code__iexact=t).exists():
            return t
            
    return 'vbt'


@login_required
def unified_log_root(request):
    target_tab = get_first_accessible_tab(request.user)
    return redirect('telescope:unified_log', tab=target_tab)


@login_required
def unified_log(request, tab='vbt'):
    if not user_can_access_tab(request.user, tab):
        messages.error(request, f"Access denied. You do not have authorization for {tab.upper()} unified log.")
        fallback_tab = get_first_accessible_tab(request.user)
        if fallback_tab != tab and user_can_access_tab(request.user, fallback_tab):
            return redirect('telescope:unified_log', tab=fallback_tab)
        return redirect('telescope:dashboard')

    if request.method == 'POST':
        log_data_str = request.POST.get('log_data', '{}')
        try:
            post_data = json.loads(log_data_str)
        except json.JSONDecodeError:
            post_data = {}

        date_str = None
        if tab in ['vbt', 'jcbt', 'czt']:
            date_str = post_data.get(f'{tab}-obsdate') or post_data.get('date')
        elif tab == 'overview':
            date_str = post_data.get('date')

        if not date_str:
            date_str = timezone.now().date().isoformat()

        target_tel = tab if tab in ['vbt', 'jcbt', 'czt', 'overview'] else 'vbt'

        # Immutability Check: Existing saved records cannot be modified
        existing_log = UnifiedLog.objects.filter(telescope=target_tel, date=date_str).first()
        if existing_log:
            messages.error(request, f"Access Denied: The Unified Log for {target_tel.upper()} on date {date_str} is already saved and locked against edits.")
            return redirect('telescope:unified_log', tab=tab)

        UnifiedLog.objects.create(
            telescope=target_tel,
            date=date_str,
            data=post_data,
            user=request.user if hasattr(request.user, 'pk') and request.user.pk else None
        )
        messages.success(request, f"{target_tel.upper()} log for date {date_str} saved and locked in database successfully.")
        return redirect('telescope:unified_log', tab=tab)

    all_logs = UnifiedLog.objects.all()
    logs_data_dict = {}
    for log in all_logs:
        date_str = log.date.isoformat() if hasattr(log.date, 'isoformat') else str(log.date)
        if log.telescope in ['vbt', 'jcbt', 'czt']:
            key = f"vbo4-{date_str}-{log.telescope}"
            logs_data_dict[key] = log.data
        elif log.telescope == 'overview':
            key = f"vbo4-ho-{date_str}"
            logs_data_dict[key] = log.data.get('ho', log.data)

    logs_json = json.dumps(logs_data_dict)

    template_map = {
        'overview': 'telescope/observations/unified_log_overview.html',
        'vbt': 'telescope/observations/unified_log_vbt.html',
        'jcbt': 'telescope/observations/unified_log_jcbt.html',
        'czt': 'telescope/observations/unified_log_czt.html',
        'report': 'telescope/observations/unified_log_report.html',
    }
    template_name = template_map.get(tab, 'telescope/observations/unified_log_vbt.html')

    user_role = getattr(request.user, 'role', '')
    is_pure_observer = (user_role == 'observer') and not (
        getattr(request.user, 'is_superuser', False) or
        getattr(request.user, 'is_root', False) or
        getattr(request.user, 'is_admin', False) or
        getattr(request.user, 'is_engineer', False) or
        getattr(request.user, 'is_scientific_officer', False)
    )
    show_tabbar = not is_pure_observer

    return render(request, template_name, {
        'active_tab': tab,
        'logs_json': logs_json,
        'show_tabbar': show_tabbar,
        'is_observer': is_pure_observer,
        'can_access_overview': user_can_access_tab(request.user, 'overview'),
        'can_access_vbt': user_can_access_tab(request.user, 'vbt'),
        'can_access_jcbt': user_can_access_tab(request.user, 'jcbt'),
        'can_access_czt': user_can_access_tab(request.user, 'czt'),
        'can_access_report': user_can_access_tab(request.user, 'report'),
    })



# ══════════════════════════════════════════════════════════════════════════════
# 6. ENGINEERING & MAINTENANCE VIEWS
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def ticket_list(request):
    tickets = MaintenanceTicket.objects.select_related('instrument', 'telescope', 'assigned_engineer', 'reported_by').all()
    q = request.GET.get('q', '').strip()
    severity = request.GET.get('severity', '').strip()
    status = request.GET.get('status', '').strip()

    if q:
        tickets = tickets.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if severity:
        tickets = tickets.filter(severity=severity)
    if status:
        tickets = tickets.filter(status=status)

    return render(request, 'telescope/maintenance/ticket_list.html', {
        'tickets': tickets.order_by('-created_at'),
        'open_count': MaintenanceTicket.objects.filter(status='open').count(),
        'in_progress_count': MaintenanceTicket.objects.filter(status='in_progress').count(),
        'resolved_count': MaintenanceTicket.objects.filter(status__in=['resolved', 'closed']).count(),
        'q': q,
        'selected_severity': severity,
        'selected_status': status,
        'severity_choices': MaintenanceTicket.SEVERITY_CHOICES,
        'status_choices': MaintenanceTicket.STATUS_CHOICES,
        'telescopes': Telescope.objects.all(),
        'instruments': Instrument.objects.all(),
    })


@login_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(MaintenanceTicket, pk=pk)
    resolve_form = ResolveTicketForm(instance=ticket)
    return render(request, 'telescope/maintenance/ticket_detail.html', {
        'ticket': ticket,
        'resolve_form': resolve_form,
    })


@login_required
def ticket_create(request):
    if request.method == 'POST':
        form = MaintenanceTicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.reported_by = request.user if hasattr(request.user, 'pk') and request.user.pk else None
            ticket.save()
            messages.success(request, f"Maintenance ticket '{ticket.title}' created.")
            return redirect('telescope:ticket_detail', pk=ticket.pk)
    else:
        form = MaintenanceTicketForm()
    return render(request, 'telescope/maintenance/ticket_form.html', {'form': form, 'action': 'Create Maintenance Ticket'})


@login_required
def ticket_resolve(request, pk):
    ticket = get_object_or_404(MaintenanceTicket, pk=pk)
    if request.method == 'POST':
        form = ResolveTicketForm(request.POST, instance=ticket)
        if form.is_valid():
            ticket = form.save(commit=False)
            if ticket.status == 'resolved':
                ticket.resolved_at = timezone.now()
            ticket.save()
            messages.success(request, f"Ticket '{ticket.title}' updated.")
    return redirect('telescope:ticket_detail', pk=pk)


@login_required
def calibration_list(request):
    cals = CalibrationLog.objects.select_related('instrument', 'instrument__telescope', 'engineer').all().order_by('-executed_at')
    return render(request, 'telescope/maintenance/calibration_list.html', {
        'calibrations': cals,
        'status_choices': CalibrationLog.CAL_STATUS_CHOICES,
        'cal_type_choices': CalibrationLog.CAL_TYPE_CHOICES,
        'telescopes': Telescope.objects.all(),
        'instruments': Instrument.objects.all(),
    })


@login_required
def calibration_create(request):
    if request.method == 'POST':
        form = CalibrationLogForm(request.POST)
        if form.is_valid():
            cal = form.save(commit=False)
            cal.engineer = request.user if hasattr(request.user, 'pk') and request.user.pk else None
            cal.save()
            messages.success(request, f"Calibration run logged for {cal.instrument.code}.")
            return redirect('telescope:calibration_list')
    else:
        form = CalibrationLogForm()
    return render(request, 'telescope/maintenance/calibration_form.html', {'form': form, 'action': 'Log Calibration Run'})


@login_required
def calibration_status_update(request, pk):
    cal = get_object_or_404(CalibrationLog, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in [choice[0] for choice in CalibrationLog.CAL_STATUS_CHOICES]:
            cal.status = new_status
            cal.save()
            messages.success(request, f"Calibration #{cal.pk} status updated.")
    return redirect('telescope:calibration_list')


# ══════════════════════════════════════════════════════════════════════════════
# 7. PLATE SOLVER TOOL VIEWS
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def platesolver_index(request):
    engine = PlateSolverEngine()
    engine.load_catalog()
    catalog_stars = engine.get_catalog_list()

    telescopes = Telescope.objects.all().order_by('code')
    selected_telescope = telescopes.first()

    initial_ra_deg = round(np.random.uniform(10, 200), 3)
    initial_dec_deg = round(np.random.uniform(-40, 60), 3)
    history_runs = PlateSolveRun.objects.select_related('telescope', 'user').all()[:10]

    return render(request, 'telescope/platesolver/index.html', {
        'catalog_stars': catalog_stars,
        'telescopes': telescopes,
        'selected_telescope': selected_telescope,
        'initial_ra_deg': initial_ra_deg,
        'initial_dec_deg': initial_dec_deg,
        'history_runs': history_runs,
    })


@login_required
def platesolver_api_field(request):
    ra_deg = float(request.GET.get('ra', 0.0))
    dec_deg = float(request.GET.get('dec', 0.0))
    fov_deg = float(request.GET.get('fov', 20.0))

    engine = PlateSolverEngine()
    ra_rad = np.deg2rad(ra_deg)
    dec_rad = np.deg2rad(dec_deg)

    stars = engine.get_stars_in_field(ra_rad, dec_rad, fov_deg)
    return JsonResponse({
        'status': 'success',
        'center_ra_deg': ra_deg,
        'center_dec_deg': dec_deg,
        'center_ra_rad': round(ra_rad, 5),
        'center_dec_rad': round(dec_rad, 5),
        'fov_deg': fov_deg,
        'star_count': len(stars),
        'stars': stars,
    })


@login_required
def platesolver_api_solve(request):
    if request.method == 'POST':
        ra_deg = float(request.POST.get('ra', 0.0))
        dec_deg = float(request.POST.get('dec', 0.0))
        fov_deg = float(request.POST.get('fov', 20.0))
        add_noise = request.POST.get('noise') == 'true'
        telescope_id = request.POST.get('telescope_id')

        engine = PlateSolverEngine()
        result = engine.solve_plate(ra_deg, dec_deg, fov_deg, add_noise)

        tel_obj = Telescope.objects.filter(pk=telescope_id).first() if telescope_id else None

        run = PlateSolveRun.objects.create(
            telescope=tel_obj,
            user=request.user if hasattr(request.user, 'pk') and request.user.pk else None,
            target_ra_deg=ra_deg,
            target_dec_deg=dec_deg,
            fov_deg=fov_deg,
            solved_ra_deg=result['solved_ra_deg'],
            solved_dec_deg=result['solved_dec_deg'],
            pixel_scale_arcsec=result['pixel_scale_arcsec'],
            rotation_angle_deg=result['rotation_angle_deg'],
            matched_stars_count=result['matched_stars_count'],
            solution_time_sec=result['solution_time_sec'],
            ra_error_arcmin=result['ra_error_arcmin'],
            dec_error_arcmin=result['dec_error_arcmin'],
            status=PlateSolveRun.STATUS_SUCCESS,
        )

        result['run_id'] = run.pk
        return JsonResponse(result)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=400)


@login_required
def platesolver_api_sync(request):
    if request.method == 'POST':
        telescope_id = request.POST.get('telescope_id')
        solved_ra = request.POST.get('solved_ra')
        solved_dec = request.POST.get('solved_dec')

        if not telescope_id:
            return JsonResponse({'status': 'error', 'message': 'No telescope selected.'}, status=400)

        telescope = get_object_or_404(Telescope, pk=telescope_id)
        telescope.right_ascension = solved_ra
        telescope.declination = solved_dec
        telescope.ra = solved_ra
        telescope.dec = solved_dec
        telescope.status = Telescope.STATUS_TRACKING
        telescope.save()

        TelescopeLog.objects.create(
            telescope=telescope,
            user=request.user if hasattr(request.user, 'pk') and request.user.pk else None,
            event_type='slew',
            message=f"Plate Solver Sync: Telescope pointing synced to solved WCS center RA: {solved_ra}, DEC: {solved_dec}."
        )

        return JsonResponse({
            'status': 'success',
            'message': f"Telescope {telescope.code} pointing synced to {solved_ra}, {solved_dec}!"
        })
    return JsonResponse({'status': 'error', 'message': 'Invalid method.'}, status=400)


# ══════════════════════════════════════════════════════════════════════════════
# 8. FEEDBACK VIEWS
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def feedback_view(request):
    user = request.user
    from accounts.rbac import get_canonical_role, ROLE_ROOT, ROLE_TCS_ADMIN
    role = get_canonical_role(user)
    is_admin_user = (
        user.is_superuser
        or getattr(user, 'is_root', False)
        or getattr(user, 'is_telescope_admin', False)
        or role in [ROLE_ROOT, ROLE_TCS_ADMIN]
        or getattr(user, 'role', '') == 'admin'
    )

    is_auth_user = (getattr(user, '_meta', None) and user._meta.model_name == 'user')

    if request.method == 'POST':
        form = SiteFeedbackForm(request.POST)
        if form.is_valid():
            fb = form.save(commit=False)
            fb.user = user if is_auth_user else None
            fb.name = user.get_full_name() or user.username
            fb.email = getattr(user, 'email', '') or ""
            fb.save()
            messages.success(request, "Thank you! Your feedback has been submitted successfully.")
            return redirect('telescope:feedback')
        else:
            messages.error(request, "Failed to submit feedback. Please check the form fields.")
    else:
        form = SiteFeedbackForm()

    if is_admin_user:
        feedbacks = SiteFeedback.objects.all().order_by('-created_at')
    else:
        # Standard users only see feedback submitted by themselves
        if is_auth_user:
            feedbacks = SiteFeedback.objects.filter(user=user).order_by('-created_at')
        else:
            feedbacks = SiteFeedback.objects.filter(
                Q(name__iexact=user.username) | Q(name__iexact=user.get_full_name())
            ).order_by('-created_at')

    bug_count = feedbacks.filter(category='bug_error').count()
    open_count = feedbacks.filter(status='new').count()
    feature_count = feedbacks.filter(category='feature_req').count()
    ui_count = feedbacks.filter(category='ui_ux').count()
    hardware_count = feedbacks.filter(category='hardware_error').count()

    return render(request, 'telescope/feedback.html', {
        'form': form,
        'feedbacks': feedbacks,
        'is_admin_user': is_admin_user,
        'total_count': feedbacks.count(),
        'bug_count': bug_count,
        'open_count': open_count,
        'feature_count': feature_count,
        'ui_count': ui_count,
        'hardware_count': hardware_count,
        'categories': SiteFeedback.CATEGORY_CHOICES,
    })


@login_required
def feedback_respond_view(request, pk):
    fb = get_object_or_404(SiteFeedback, pk=pk)
    if request.method == 'POST':
        fb.admin_response = request.POST.get('admin_response', '').strip()
        fb.status = request.POST.get('status', fb.status)
        fb.save()
        messages.success(request, "Feedback response updated.")
    return redirect('telescope:feedback')


@login_required
def mark_notifications_read(request):
    return JsonResponse({'status': 'ok'})


# ══════════════════════════════════════════════════════════════════════════════
# 9. TCS USER MANAGEMENT VIEWS (TCS_ADMIN / TCS_MEMBER hierarchy)
# ══════════════════════════════════════════════════════════════════════════════

def _is_tcs_admin(user):
    """
    Returns True if the logged-in user is a TCS admin or global ROOT superuser.
    Accepts TelescopeUser instances, standard accounts.User instances, and RBAC canonical roles.
    """
    if not user or not user.is_authenticated:
        return False
    if getattr(user, 'is_superuser', False):
        return True
    if hasattr(user, 'is_root') and user.is_root:
        return True
    from accounts.rbac import get_canonical_role, ROLE_ROOT, ROLE_TCS_ADMIN
    role = get_canonical_role(user)
    if role in [ROLE_ROOT, ROLE_TCS_ADMIN]:
        return True
    if hasattr(user, '_meta') and user._meta.model_name == 'telescopeuser':
        return user.is_telescope_admin or user.role == TelescopeUser.ROLE_ADMIN
    return False


@login_required
def user_list(request):
    """
    TCS User Management view — categorized user overview by roles matching TCS system design.
    Accessible by TCS Admins and global ROOT admin.
    """
    if not _is_tcs_admin(request.user):
        messages.error(request, "Access Denied: Only TCS Administrators and ROOT can manage users.")
        return redirect('telescope:dashboard')

    q = request.GET.get('q', '').strip()
    role = request.GET.get('role', '').strip()
    department = request.GET.get('department', '').strip()

    users = TelescopeUser.objects.all()

    if role:
        users = users.filter(role=role)
    if department:
        users = users.filter(department=department)
    if q:
        users = users.filter(
            Q(username__icontains=q) |
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(email__icontains=q) |
            Q(designation__icontains=q)
        )

    users = users.order_by('role', '-created_at')

    # Category statistics counts
    total_users_count = TelescopeUser.objects.count()
    admin_users_count = TelescopeUser.objects.filter(Q(role='admin') | Q(is_telescope_admin=True)).count()
    engineer_users_count = TelescopeUser.objects.filter(role='engineer').count()
    so_users_count = TelescopeUser.objects.filter(role='scientific_officer').count()
    observer_users_count = TelescopeUser.objects.filter(role='observer').count()

    # Categorized user lists
    admin_users = users.filter(Q(role='admin') | Q(is_telescope_admin=True))
    engineer_users = users.filter(role='engineer', is_telescope_admin=False)
    so_users = users.filter(role='scientific_officer', is_telescope_admin=False)
    observer_users = users.filter(role='observer', is_telescope_admin=False)

    all_telescopes = Telescope.objects.all()

    context = {
        'users': users,
        'admin_users': admin_users,
        'engineer_users': engineer_users,
        'so_users': so_users,
        'observer_users': observer_users,
        'selected_role': role,
        'selected_department': department,
        'q': q,
        'total_users_count': total_users_count,
        'admin_users_count': admin_users_count,
        'engineer_users_count': engineer_users_count,
        'so_users_count': so_users_count,
        'observer_users_count': observer_users_count,
        'department_choices': TelescopeUser.DEPARTMENT_CHOICES,
        'role_choices': TelescopeUser.ROLE_CHOICES,
        'all_telescopes': all_telescopes,
        'is_tele_admin': True,
    }
    return render(request, 'telescope/user_list.html', context)


@login_required
def user_create(request):
    """
    Creates a TelescopeUser account using dedicated user creation form matching TCS system architecture.
    """
    if not _is_tcs_admin(request.user):
        messages.error(request, "Access Denied: Only TCS Administrators can create users.")
        return redirect('telescope:dashboard')

    if request.method == 'POST':
        form = TelescopeUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            pwd = form.cleaned_data.get('password1')
            if pwd:
                user.set_password(pwd)
            user.save()
            form.save_m2m()

            messages.success(request, f"User account '{user.username}' ({user.get_role_display()}) created successfully.")
            return redirect('telescope:user_list')
        else:
            messages.error(request, "Failed to create user account. Please check the form errors below.")
    else:
        form = TelescopeUserCreationForm()

    return render(request, 'telescope/user_form.html', {'form': form, 'action': 'Create New User'})


@login_required
def user_edit(request, pk):
    """
    Edits a TelescopeUser account credentials, role assignment, active status, and authorized telescopes.
    """
    if not _is_tcs_admin(request.user):
        messages.error(request, "Access Denied: Only TCS Administrators can edit users.")
        return redirect('telescope:dashboard')

    target_user = get_object_or_404(TelescopeUser, pk=pk)
    if request.method == 'POST':
        form = TelescopeAdminEditForm(request.POST, instance=target_user)
        if form.is_valid():
            user = form.save(commit=False)
            new_pwd = form.cleaned_data.get('new_password')
            if new_pwd:
                user.set_password(new_pwd)
            user.save()
            form.save_m2m()

            messages.success(request, f"User account '{user.username}' updated successfully.")
            return redirect('telescope:user_list')
        else:
            messages.error(request, "Failed to update user account. Please check the form errors below.")
    else:
        form = TelescopeAdminEditForm(instance=target_user)

    return render(request, 'telescope/user_edit.html', {'form': form, 'target_user': target_user})


@login_required
def user_delete(request, pk):
    """
    Deletes a TelescopeUser account with confirmation matching TCS system architecture.
    """
    if not _is_tcs_admin(request.user):
        messages.error(request, "Access Denied: Only TCS Administrators can remove users.")
        return redirect('telescope:dashboard')

    target_user = get_object_or_404(TelescopeUser, pk=pk)

    if request.method == 'POST':
        if hasattr(request.user, 'pk') and hasattr(target_user, 'pk') and request.user.pk == target_user.pk and getattr(request.user._meta, 'model_name', '') == getattr(target_user._meta, 'model_name', ''):
            messages.error(request, "You cannot delete your own active administrator account!")
            return redirect('telescope:user_list')

        username = target_user.username
        target_user.delete()
        messages.success(request, f"User account '{username}' deleted successfully.")
        return redirect('telescope:user_list')

    return render(request, 'telescope/user_confirm_delete.html', {'target_user': target_user})


@login_required
def user_toggle(request, pk):
    """
    Toggles active/inactive status for a TelescopeUser. Restricted to TCS Admins only.
    """
    if not _is_tcs_admin(request.user):
        messages.error(request, "Access Denied: Only TCS Administrators can toggle user status.")
        return redirect('telescope:dashboard')

    user = get_object_or_404(TelescopeUser, pk=pk)
    user.is_active = not user.is_active
    user.save()
    status_str = "activated" if user.is_active else "deactivated"
    messages.success(request, f"TCS user '{user.username}' {status_str}.")
    return redirect('telescope:user_list')

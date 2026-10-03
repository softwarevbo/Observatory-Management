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
    CalibrationLogForm, SiteFeedbackForm, TelescopeUserForm
)
from .platesolver.solver_engine import PlateSolverEngine


def ensure_default_telescopes():
    """
    Checks if default telescope seed instances exist in the database;
    if none are found, initializes core observatory telescope records.
    """
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

    return render(request, template_name, {
        'telescope': telescope,
        'targets': targets,
        'slew_form': slew_form,
        'logs': logs,
        'instruments': instruments,
        'discussions': discussions,
        'discussion_form': discussion_form,
        'can_control': True,
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


@login_required
def slew_telescope(request, pk):
    telescope = get_object_or_404(Telescope, pk=pk)
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
    telescopes = Telescope.objects.all().order_by('code')
    selected_telescope_id = request.GET.get('telescope', '')
    selected_category = request.GET.get('category', '')
    search_query = request.GET.get('q', '').strip()

    discussions = TelescopeDiscussion.objects.select_related('telescope', 'user').annotate(reply_count=Count('replies'))

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


@login_required
def unified_log_root(request):
    return redirect('telescope:unified_log', tab='vbt')


@login_required
def unified_log(request, tab='vbt'):
    if request.method == 'POST':
        log_data_str = request.POST.get('log_data', '{}')
        try:
            post_data = json.loads(log_data_str)
        except json.JSONDecodeError:
            post_data = {}

        date_str = post_data.get('date') or timezone.now().date().isoformat()
        target_tel = tab if tab in ['vbt', 'jcbt', 'czt', 'overview'] else 'vbt'

        existing_log = UnifiedLog.objects.filter(telescope=target_tel, date=date_str).first()
        if existing_log:
            messages.error(request, f"Log for {target_tel.upper()} on date {date_str} already exists.")
            return redirect('telescope:unified_log', tab=tab)

        UnifiedLog.objects.create(
            telescope=target_tel,
            date=date_str,
            data=post_data,
            user=request.user if hasattr(request.user, 'pk') and request.user.pk else None
        )
        messages.success(request, f"{target_tel.upper()} log for date {date_str} saved.")
        return redirect('telescope:unified_log', tab=tab)

    all_logs = UnifiedLog.objects.all()
    logs_data_dict = {}
    for log in all_logs:
        date_str = str(log.date)
        if log.telescope in ['vbt', 'jcbt', 'czt']:
            logs_data_dict[f"vbo4-{date_str}-{log.telescope}"] = log.data
        elif log.telescope == 'overview':
            logs_data_dict[f"vbo4-ho-{date_str}"] = log.data.get('ho', log.data)

    template_map = {
        'overview': 'telescope/observations/unified_log_overview.html',
        'vbt': 'telescope/observations/unified_log_vbt.html',
        'jcbt': 'telescope/observations/unified_log_jcbt.html',
        'czt': 'telescope/observations/unified_log_czt.html',
        'report': 'telescope/observations/unified_log_report.html',
    }
    template_name = template_map.get(tab, 'telescope/observations/unified_log_vbt.html')

    return render(request, template_name, {
        'active_tab': tab,
        'logs_json': json.dumps(logs_data_dict),
        'show_tabbar': True,
        'can_access_overview': True,
        'can_access_vbt': True,
        'can_access_jcbt': True,
        'can_access_czt': True,
        'can_access_report': True,
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
    if request.method == 'POST':
        form = SiteFeedbackForm(request.POST)
        if form.is_valid():
            fb = form.save(commit=False)
            fb.user = user if hasattr(user, 'pk') and user.pk else None
            fb.save()
            messages.success(request, "Feedback submitted successfully.")
            return redirect('telescope:feedback')
    else:
        form = SiteFeedbackForm()

    feedbacks = SiteFeedback.objects.all().order_by('-created_at')
    return render(request, 'telescope/feedback.html', {
        'form': form,
        'feedbacks': feedbacks,
        'total_count': feedbacks.count(),
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

@login_required
def user_list(request):
    """
    TCS User Management view.
    Role options are strictly TCS_ADMIN and TCS_MEMBER.
    ROOT is the global Super Admin across the application and is not a TCS role option.
    """
    search = request.GET.get('q', '').strip()
    selected_role = request.GET.get('role', '').strip()
    users = TelescopeUser.objects.all().order_by('-created_at')

    if search:
        users = users.filter(Q(username__icontains=search) | Q(email__icontains=search))

    admin_users = users.filter(models.Q(role='admin') | models.Q(is_telescope_admin=True))
    observer_users = users.filter(role='operator', is_telescope_admin=False)

    stats = {
        'total': users.count(),
        'admins': admin_users.count(),
        'members': observer_users.count(),
        'active': users.filter(is_active=True).count(),
    }

    return render(request, 'telescope/user_list.html', {
        'users': users,
        'admin_users': admin_users,
        'observer_users': observer_users,
        'admin_users_count': admin_users.count(),
        'observer_users_count': observer_users.count(),
        'total_users_count': users.count(),
        'selected_role': selected_role,
        'stats': stats,
        'search': search,
        'q': search,
    })


@login_required
def user_create(request):
    """
    Creates a TelescopeUser account.
    Allowed roles: TCS_ADMIN ('admin') and TCS_MEMBER ('operator').
    ROOT cannot be selected as a TCS user role.
    """
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        email = request.POST.get('email', '').strip()
        selected_role = request.POST.get('role', 'operator').strip()
        is_tele_admin = (selected_role == 'admin') or (request.POST.get('is_telescope_admin') == 'on')

        if not username or not password:
            messages.error(request, "Username and password are required.")
            return redirect('telescope:user_list')

        if TelescopeUser.objects.filter(username=username).exists():
            messages.error(request, f"Username '{username}' already exists.")
            return redirect('telescope:user_list')

        # Prevent creating ROOT role inside TCS
        role_final = "admin" if is_tele_admin else "operator"

        user = TelescopeUser.objects.create(
            username=username,
            email=email or None,
            role=role_final,
            is_active=request.POST.get('is_active') == 'on',
            is_telescope_admin=is_tele_admin,
            can_operate_vbt=request.POST.get('can_operate_vbt') == 'on',
            can_operate_jcbt=request.POST.get('can_operate_jcbt') == 'on',
            can_operate_zeiss=request.POST.get('can_operate_zeiss') == 'on',
            can_operate_cassegrain=request.POST.get('can_operate_cassegrain') == 'on',
            can_operate_schmidt=request.POST.get('can_operate_schmidt') == 'on',
            can_command_dome=request.POST.get('can_command_dome') == 'on',
            can_trigger_exposures=request.POST.get('can_trigger_exposures') == 'on',
        )
        user.set_password(password)
        messages.success(request, f"TCS user '{username}' created successfully.")

    return redirect('telescope:user_list')


@login_required
def user_edit(request, pk):
    user = get_object_or_404(TelescopeUser, pk=pk)
    if request.method == 'POST':
        user.email = request.POST.get('email', '').strip() or None
        user.is_active = request.POST.get('is_active') == 'on'

        selected_role = request.POST.get('role', user.role).strip()
        is_admin_check = (selected_role == 'admin') or (request.POST.get('is_telescope_admin') == 'on')

        user.role = "admin" if is_admin_check else "operator"
        user.is_telescope_admin = is_admin_check

        permission_fields = [
            'can_operate_vbt', 'can_operate_jcbt', 'can_operate_zeiss',
            'can_operate_cassegrain', 'can_operate_schmidt',
            'can_command_dome', 'can_trigger_exposures'
        ]
        for field in permission_fields:
            setattr(user, field, request.POST.get(field) == 'on')

        password = request.POST.get('password', '').strip()
        if password:
            user.set_password(password)
        else:
            user.save()

        messages.success(request, f"TCS user '{user.username}' updated successfully.")

    return redirect('telescope:user_list')


@login_required
def user_delete(request, pk):
    user = get_object_or_404(TelescopeUser, pk=pk)
    username = user.username
    user.is_active = False
    user.save()
    messages.success(request, f"TCS user '{username}' deactivated.")
    return redirect('telescope:user_list')


@login_required
def user_toggle(request, pk):
    user = get_object_or_404(TelescopeUser, pk=pk)
    user.is_active = not user.is_active
    user.save()
    messages.success(request, f"TCS user '{user.username}' status updated.")
    return redirect('telescope:user_list')

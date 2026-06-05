from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.text import slugify
from .models import Telescope

def ensure_default_telescopes():
    """
    Checks if default telescope seed instances exist in the database;
    if none are found, initializes the core Kavalur Observatory instrumentation records.
    """
    if Telescope.objects.count() == 0:
        Telescope.objects.create(
            id_name="vbt_234",
            name="Vainu Bappu Telescope (VBT)",
            aperture="2.34 Meter",
            type="Reflector (Cassegrain / Prime Focus)",
            status="observing",
            current_target="NGC 5194 (M51 Whirlpool Galaxy)",
            ra="13h 29m 52.7s",
            dec="+47° 11′ 43″",
            dome="Open",
            focus="Cassegrain",
            instrument="OMC (Optical Mosaic Camera)",
            ccd_temp="-110°C",
            tracking="Enabled",
            image_url="https://www.iiap.res.in/centers/vbo/vbt/vbt.jpg",
            description="The 90-inch (2.34m) Vainu Bappu Telescope is the flagship instrument at VBO. It has been operational since 1986. Located at longitude 78° 50' E and latitude 12° 34' N, it sits at 725m elevation in the Javadi Hills. Key instruments include the OMR Spectrograph, the Optical Mosaic Camera, and the high-resolution Echelle Spectrograph. It is mounted on an equatorial horseshoe structure.",
            history="Inaugurated on January 6, 1986 by the Prime Minister of India, Rajiv Gandhi, who named it after the founder Dr. M.K. Vainu Bappu. The telescope was designed and fabricated entirely in India."
        )
        Telescope.objects.create(
            id_name="jcbt_130",
            name="J.C. Bhattacharya Telescope (JCBT)",
            aperture="1.3 Meter",
            type="Ritchey-Chrétien Reflector",
            status="observing",
            current_target="HAT-P-12b (Exoplanet Transit)",
            ra="16h 41m 02.4s",
            dec="+35° 40′ 33″",
            dome="Open",
            focus="RC Focus",
            instrument="High Resolution Spectrograph",
            ccd_temp="-95°C",
            tracking="Enabled",
            image_url="https://www.iiap.res.in/centers/vbo/jcbt/jcbt.jpg",
            description="The 1.3m J.C. Bhattacharya Telescope (JCBT) was commissioned in 2014. It is a Ritchey-Chrétien reflector equipped with an equatorial fork mount. It features dual focus ports and is used for photometry, imaging, and high-resolution spectroscopy of stars, active galactic nuclei, and solar system bodies.",
            history="Named in honor of Dr. J.C. Bhattacharya, a former director of IIA who contributed significantly to astronomical instrumentation in India. The telescope is extensively used by university groups."
        )
        Telescope.objects.create(
            id_name="zeiss_100",
            name="Carl Zeiss Telescope",
            aperture="1.0 Meter",
            type="Reflector",
            status="idle",
            current_target="None",
            ra="00h 00m 00s",
            dec="+00° 00′ 00″",
            dome="Closed",
            focus="Cassegrain",
            instrument="UAGS Spectrograph",
            ccd_temp="-80°C",
            tracking="Disabled",
            image_url="https://www.iiap.res.in/centers/vbo/czt/czt.jpg",
            description="The 40-inch (1.0m) Carl Zeiss Telescope was established at Kavalur in 1972. It played a historic role in discovery of rings of Uranus and atmosphere of Ganymede. It is an equatorial mounting reflector supporting Cassegrain and Coude focus options.",
            history="Acquired from Carl Zeiss, Germany. It was the main workhorse of Kavalur Observatory before the commissioning of VBT. It is highly valued for stellar occultation research."
        )
        Telescope.objects.create(
            id_name="cassegrain_75",
            name="75cm Cassegrain Telescope",
            aperture="0.75 Meter",
            type="Cassegrain Reflector",
            status="maintenance",
            current_target="None",
            ra="N/A",
            dec="N/A",
            dome="Closed",
            focus="N/A",
            instrument="None",
            ccd_temp="Ambient",
            tracking="Disabled",
            description="The 75cm Cassegrain Telescope was built in-house at the IIA workshops. It is primarily used for stellar photometry and spectroscopic observations of bright objects.",
            history="Developed entirely within the Institute of Astrophysics, showcasing local engineering and precision design capabilities in the late 20th century."
        )
        Telescope.objects.create(
            id_name="schmidt_45",
            name="45cm Schmidt Telescope",
            aperture="0.45 Meter",
            type="Schmidt Camera",
            status="idle",
            current_target="None",
            ra="00h 00m 00s",
            dec="+00° 00′ 00″",
            dome="Closed",
            focus="Prime Focus",
            instrument="Wide Field CCD Camera",
            ccd_temp="-85°C",
            tracking="Disabled",
            description="The 45cm Schmidt Telescope is a wide-field telescope used for sky surveys, comet tracking, asteroid detection, and transient follow-ups.",
            history="Constructed in the 1980s, this telescope continues to support student projects and wide-field astronomical imaging surveys."
        )

@login_required
def dashboard(request):
    """
    Renders the telescope monitoring dashboard displaying status trackers and weather logs.
    """
    # Enforce telescope access permissions
    if not request.user.is_superuser and not request.user.can_access_telescope:
        messages.error(request, "Access Denied: You do not have permission to access the Telescope Control System.")
        return redirect("accounts:login")
    
    # Ensure seed instruments exist
    ensure_default_telescopes()
    telescopes = Telescope.objects.all()
    
    context = {
        "telescopes": telescopes,
        "observatory": {
            "name": "Kavalur Vainu Bappu Observatory",
            "location": "Kavalur, Javadi Hills, Tamil Nadu, India",
            "elevation": "725 meters (2,379 ft) ASL",
            "coordinates": "12°34'35\" N, 78°49'38\" E",
            "established": "1968 (named after Dr. M. K. Vainu Bappu)",
        },
        "weather": {
            "temp": "18.2 °C",
            "humidity": "42%",
            "wind": "12.4 km/h ENE",
            "clouds": "Clear Sky",
            "seeing": "1.2 arcsec (Excellent)",
            "pressure": "934 hPa",
        }
    }
    return render(request, "telescope/dashboard.html", context)

@login_required
def telescope_detail(request, pk):
    """
    Displays the technical specifications and real-time feed indicators for a single telescope.
    """
    if not request.user.is_superuser and not request.user.can_access_telescope:
        messages.error(request, "Access Denied.")
        return redirect("accounts:login")
    
    telescope = get_object_or_404(Telescope, pk=pk)
    return render(request, "telescope/detail.html", {"t": telescope})

@login_required
def telescope_create(request):
    """
    Creates a new telescope record inside the control registry system.
    """
    # Enforce administrative access level check
    if not request.user.is_superuser and not request.user.is_telescope_admin:
        messages.error(request, "Access Denied: Only Telescope Control System Administrators can add new telescopes.")
        return redirect("telescope:dashboard")
    
    if request.method == "POST":
        name = request.POST.get("name")
        aperture = request.POST.get("aperture")
        type_str = request.POST.get("type")
        status = request.POST.get("status", "idle")
        current_target = request.POST.get("current_target", "None")
        ra = request.POST.get("ra", "00h 00m 00s")
        dec = request.POST.get("dec", "+00° 00′ 00″")
        dome = request.POST.get("dome", "Closed")
        focus = request.POST.get("focus", "Cassegrain")
        instrument = request.POST.get("instrument", "None")
        ccd_temp = request.POST.get("ccd_temp", "Ambient")
        tracking = request.POST.get("tracking", "Disabled")
        image_url = request.POST.get("image_url")
        description = request.POST.get("description", "")
        history = request.POST.get("history", "")
        
        # Generate slugified system identifier
        id_name = slugify(name).replace("-", "_")
        
        tele = Telescope.objects.create(
            id_name=id_name,
            name=name,
            aperture=aperture,
            type=type_str,
            status=status,
            current_target=current_target,
            ra=ra,
            dec=dec,
            dome=dome,
            focus=focus,
            instrument=instrument,
            ccd_temp=ccd_temp,
            tracking=tracking,
            image_url=image_url,
            description=description,
            history=history
        )
        if request.FILES.get("image"):
            tele.image = request.FILES.get("image")
            tele.save()
            
        messages.success(request, f"Telescope '{name}' added successfully.")
        return redirect("telescope:dashboard")
    
    return render(request, "telescope/form.html", {"action": "Add"})

@login_required
def telescope_edit(request, pk):
    """
    Edits target targets, tracking controls, dome state and configurations of an existing telescope.
    """
    # Enforce telescope control system admin authorization checks
    if not request.user.is_superuser and not request.user.is_telescope_admin:
        messages.error(request, "Access Denied: Only Telescope Control System Administrators can edit telescopes.")
        return redirect("telescope:dashboard")
    
    tele = get_object_or_404(Telescope, pk=pk)
    
    if request.method == "POST":
        tele.name = request.POST.get("name")
        tele.aperture = request.POST.get("aperture")
        tele.type = request.POST.get("type")
        tele.status = request.POST.get("status")
        tele.current_target = request.POST.get("current_target")
        tele.ra = request.POST.get("ra")
        tele.dec = request.POST.get("dec")
        tele.dome = request.POST.get("dome")
        tele.focus = request.POST.get("focus")
        tele.instrument = request.POST.get("instrument")
        tele.ccd_temp = request.POST.get("ccd_temp")
        tele.tracking = request.POST.get("tracking")
        tele.image_url = request.POST.get("image_url")
        tele.description = request.POST.get("description")
        tele.history = request.POST.get("history")
        
        if request.FILES.get("image"):
            tele.image = request.FILES.get("image")
            
        tele.save()
        messages.success(request, f"Telescope '{tele.name}' updated successfully.")
        return redirect("telescope:dashboard")
        
    return render(request, "telescope/form.html", {"t": tele, "action": "Edit"})

@login_required
def telescope_delete(request, pk):
    """
    Deletes a telescope registration record.
    """
    if not request.user.is_superuser and not request.user.is_telescope_admin:
        messages.error(request, "Access Denied: Only Telescope Control System Administrators can delete telescopes.")
        return redirect("telescope:dashboard")
    
    tele = get_object_or_404(Telescope, pk=pk)
    name = tele.name
    tele.delete()
    messages.success(request, f"Telescope '{name}' deleted successfully.")
    return redirect("telescope:dashboard")

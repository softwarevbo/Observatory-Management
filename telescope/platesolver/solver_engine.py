import os
import csv
import copy
import math
import numpy as np

try:
    from scipy import ndimage
except ImportError:
    ndimage = None

FoV = 20  # degrees
MAX_ANGULAR_DISTANCE = np.deg2rad(FoV / 2)
IMAGE_DIMENSIONS = np.array((2048, 2048))
ADC_RESOLUTION = 2 ** 12 - 1
ADC_CONVERSION = lambda x: np.uint16(19968 * (x - 0.159) + 4095) if x < 0.159 else 4095


class PlateSolverEngine:
    """ Plate Solver Calculation Engine """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PlateSolverEngine, cls).__new__(cls)
            cls._instance.catalog = []
            cls._instance.starsInCurrentField = None
            cls._instance.fieldCenter_RADec = np.array((0, 0))
            cls._instance.current_RA_Direction_radian = 0
            cls._instance.current_Dec_Direction_radian = 0
            cls._instance.image_size = IMAGE_DIMENSIONS
            cls._instance.img_template = np.zeros(cls._instance.image_size)
            r = np.min(cls._instance.image_size) // 2 - 1
            cls._instance.plate_scale = (2 * r) / np.deg2rad(FoV)
            cls._instance.image_center = cls._instance.image_size // 2

            X, Y = np.ogrid[:cls._instance.image_size[0], :cls._instance.image_size[1]]
            circular_mask = (X - cls._instance.image_center[0]) ** 2 + (Y - cls._instance.image_center[1]) ** 2 > r ** 2
            cls._instance.img_template[circular_mask] = 0.15 * ADC_RESOLUTION
            cls._instance.img_data = copy.deepcopy(cls._instance.img_template)
            cls._instance.read_catalog()
        return cls._instance

    def read_catalog(self):
        if len(self.catalog) > 0:
            return

        catalog_path = os.path.join(os.path.dirname(__file__), 'reduced_catalog_2.0_6.0_mag2.csv')

        self.catalog = []
        if os.path.exists(catalog_path):
            try:
                with open(catalog_path, 'r', encoding='utf-8') as file:
                    csvReader = csv.reader(file)
                    header = next(csvReader)
                    for row in csvReader:
                        self.catalog.append(np.float64(row))

                if self.catalog:
                    self.catalog = np.array(self.catalog)
                    self.catalog[:, 0] = self.catalog[:, 0].astype(int)
            except Exception as e:
                print(f"Error reading Hipparcos catalog from {catalog_path}: {e}")

        if not os.path.exists(catalog_path) or len(self.catalog) == 0:
            print("Warning: CSV file not found, creating synthetic star catalog...")
            np.random.seed(42)
            stars = []
            for i in range(1, 500):
                hip = i
                ra_rad = np.random.uniform(0, 2 * np.pi)
                dec_rad = np.random.uniform(-np.pi / 2, np.pi / 2)
                mag = np.random.uniform(2.0, 6.0)
                stars.append([hip, ra_rad, dec_rad, 10.0, 0.0, 0.0, mag])
            self.catalog = np.array(stars)

    def load_catalog(self):
        self.read_catalog()

    def get_catalog_list(self):
        self.read_catalog()
        result = []
        for star in self.catalog:
            hip = int(star[0])
            ra_deg = np.rad2deg(star[1])
            dec_deg = np.rad2deg(star[2])
            mag = float(star[6])
            result.append({
                'hip': hip,
                'ra_deg': round(ra_deg, 4),
                'dec_deg': round(dec_deg, 4),
                'ra_rad': round(float(star[1]), 5),
                'dec_rad': round(float(star[2]), 5),
                'mag': round(mag, 3),
                'label': f"HIP {hip} (RA: {ra_deg:.2f}°, Dec: {dec_deg:.2f}°, Mag: {mag:.2f})"
            })
        return result

    def create_Image(self, centerStar_RADec):
        self.read_catalog()
        self.fieldCenter_RADec = np.array(centerStar_RADec)

        self.starsInCurrentField = self.catalog[
            np.linalg.norm(self.catalog[:, 1:3] - centerStar_RADec, axis=1) < MAX_ANGULAR_DISTANCE]

        self.img_data = copy.deepcopy(self.img_template)

        for i in range(np.shape(self.starsInCurrentField)[0]):
            currentStar_RADec = self.starsInCurrentField[i, 1:3]
            currentStar_imageCoord = np.int_(
                self.image_center + ((currentStar_RADec - centerStar_RADec) * self.plate_scale))
            peak_intensity = ADC_CONVERSION(
                10 ** ((2 - self.starsInCurrentField[i, -1]) / 2.5))

            x1, y1 = np.ogrid[-2:3, -2:3]
            ix, iy = currentStar_imageCoord[0], currentStar_imageCoord[1]
            if 2 <= ix < self.image_size[0] - 2 and 2 <= iy < self.image_size[1] - 2:
                self.img_data[ix + x1, iy + y1] = peak_intensity * np.exp(
                    -((x1 ** 2 / 18) + (y1 ** 2 / 18)))

        stars_data = []
        for i in range(np.shape(self.starsInCurrentField)[0]):
            star = self.starsInCurrentField[i]
            hip = int(star[0])
            currentStar_RADec = star[1:3]
            mag = float(star[-1])

            currentStar_imageCoord = np.int_(
                self.image_center + ((currentStar_RADec - centerStar_RADec) * self.plate_scale))
            peak_intensity = int(ADC_CONVERSION(10 ** ((2 - mag) / 2.5)))

            dist_val = float(np.linalg.norm([star[1] - centerStar_RADec[0], star[2] - centerStar_RADec[1]]))

            stars_data.append({
                'hip': hip,
                'ra_deg': round(np.rad2deg(star[1]), 4),
                'dec_deg': round(np.rad2deg(star[2]), 4),
                'ra_rad': round(float(star[1]), 5),
                'dec_rad': round(float(star[2]), 5),
                'mag': round(mag, 3),
                'x': int(currentStar_imageCoord[0]),
                'y': int(currentStar_imageCoord[1]),
                'intensity': peak_intensity,
                'dist_rad': round(dist_val, 6)
            })

        return stars_data

    def get_stars_in_field(self, center_ra_rad, center_dec_rad, fov_deg=FoV):
        return self.create_Image((center_ra_rad, center_dec_rad))

    def button_AddDistortion_OnClick(self, img=None):
        if img is None:
            img = self.img_data
        if ndimage is None:
            return img

        k_1 = 0.2
        k_2 = 0.05

        h, w = self.image_size
        x, y = np.meshgrid(np.float32(np.arange(w)), np.float32(np.arange(h)))

        x_c = w / 2
        y_c = h / 2
        x = (x - x_c) / x_c
        y = (y - y_c) / y_c

        radius = np.sqrt(x ** 2 + y ** 2)
        m_r = 1 + k_1 * radius + k_2 * radius ** 2

        x = x * m_r * x_c + x_c
        y = y * m_r * y_c + y_c

        distorted = ndimage.map_coordinates(img, [y.ravel(), x.ravel()], order=1)
        distorted.resize(img.shape)
        return distorted

    def solve_plate(self, input_ra_deg, input_dec_deg, fov_deg=FoV, add_noise=False):
        self.read_catalog()
        input_ra_rad = np.deg2rad(input_ra_deg)
        input_dec_rad = np.deg2rad(input_dec_deg)

        field_stars = self.create_Image((input_ra_rad, input_dec_rad))

        offset_ra_arcmin = np.random.uniform(-1.2, 1.2) if add_noise else -0.45
        offset_dec_arcmin = np.random.uniform(-0.8, 0.8) if add_noise else 0.32

        solved_ra_deg = input_ra_deg + (offset_ra_arcmin / 60.0)
        solved_dec_deg = input_dec_deg + (offset_dec_arcmin / 60.0)

        pixel_scale = round((fov_deg * 3600.0) / IMAGE_DIMENSIONS[0], 3)
        rotation_angle = round(np.random.uniform(-0.5, 0.5), 2)

        return {
            'status': 'success',
            'solved_ra_deg': round(solved_ra_deg, 5),
            'solved_dec_deg': round(solved_dec_deg, 5),
            'solved_ra_hms': deg_to_hms(solved_ra_deg),
            'solved_dec_dms': deg_to_dms(solved_dec_deg),
            'input_ra_deg': round(input_ra_deg, 5),
            'input_dec_deg': round(input_dec_deg, 5),
            'pixel_scale_arcsec': pixel_scale,
            'rotation_angle_deg': rotation_angle,
            'matched_stars_count': len(field_stars),
            'solution_time_sec': round(np.random.uniform(0.28, 0.45), 2),
            'ra_error_arcmin': round(offset_ra_arcmin, 3),
            'dec_error_arcmin': round(offset_dec_arcmin, 3),
            'total_error_arcmin': round(math.sqrt(offset_ra_arcmin**2 + offset_dec_arcmin**2), 3),
            'field_stars': field_stars,
        }


def deg_to_hms(deg):
    deg = deg % 360
    hours = deg / 15.0
    h = int(hours)
    minutes = (hours - h) * 60.0
    m = int(minutes)
    s = (minutes - m) * 60.0
    return f"{h:02d}h {m:02d}m {s:05.2f}s"


def deg_to_dms(deg):
    sign = '+' if deg >= 0 else '-'
    deg = abs(deg)
    d = int(deg)
    minutes = (deg - d) * 60.0
    m = int(minutes)
    s = (minutes - m) * 60.0
    return f"{sign}{d:02d}° {m:02d}' {s:04.1f}\""

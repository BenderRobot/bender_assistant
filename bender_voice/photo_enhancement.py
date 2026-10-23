"""Conservative, deterministic photo correction for vision, derived from the original."""
from io import BytesIO
import math

from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError

from .hardware import HardwareError

MAX_BYTES = 4_000_000
MAX_PIXELS = 8_000_000


def percentile(histogram, fraction):
    target = max(1, math.ceil(sum(histogram) * fraction))
    count = 0
    for value, frequency in enumerate(histogram):
        count += frequency
        if count >= target:
            return value
    return 255


def enhance_photo(original):
    if not 0 < len(original) <= MAX_BYTES:
        raise HardwareError('Photo vide ou trop volumineuse pour la correction automatique')
    try:
        with Image.open(BytesIO(original)) as source:
            if source.format != 'JPEG' or not 0 < source.width * source.height <= MAX_PIXELS:
                raise HardwareError('Photo JPEG invalide ou dimensions trop grandes')
            rgb = ImageOps.exif_transpose(source).convert('RGB')
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise HardwareError('Photo illisible ; reprendre une capture avant l’analyse') from exc

    luminance, blue, red = rgb.convert('YCbCr').split()
    histogram = luminance.histogram()
    low, middle, high = [percentile(histogram, p) for p in (0.01, 0.5, 0.99)]
    warnings, operations = [], []
    highlight_fraction = sum(histogram[250:]) / sum(histogram)
    if highlight_fraction > 0.05:
        warnings.append('Des zones très claires peuvent rester sans détails ; réduire l’exposition si nécessaire.')

    gamma = 1.0
    black, white = 0, 255
    if high - low >= 24:
        # Limit the stretch and gamma so room lighting or white walls cannot trigger
        # an aggressive equalization. Only luminance changes, not separate RGB gains.
        black, white = min(low, 24), max(high, 231)
        if middle < 85 or middle > 175:
            target = 120 if middle < 85 else 150
            gamma = max(0.8, min(1.25, math.log(target / 255) / math.log(max(1, min(254, middle)) / 255)))
        curve = []
        for value in range(256):
            normalized = max(0, min(1, (value - black) / (white - black)))
            corrected = 255 * normalized ** gamma
            curve.append(round(0.25 * value + 0.75 * corrected))
        luminance = luminance.point(curve)
        if black or white < 255:
            operations.append('Contraste doux adapté à la photo')
        if gamma != 1:
            operations.append('Luminosité adaptée à la photo')
        luminance = luminance.filter(ImageFilter.UnsharpMask(radius=1, percent=30, threshold=5))
        operations.append('Netteté légère')
    else:
        warnings.append('Image peu contrastée ou presque uniforme : amélioration limitée.')

    corrected = Image.merge('YCbCr', (luminance, blue, red)).convert('RGB')
    output = BytesIO()
    for quality in (92, 85, 75, 65):
        output.seek(0); output.truncate()
        corrected.save(output, format='JPEG', quality=quality, subsampling=0, optimize=True)
        if output.tell() <= MAX_BYTES:
            break
    else:
        raise HardwareError('Photo corrigée trop volumineuse ; reprendre une capture de résolution inférieure')
    return output.getvalue(), dict(enabled=True, method='photometric-v1', operations=operations,
        warnings=warnings, gamma=round(gamma, 3), highlights_percent=round(100 * highlight_fraction, 1),
        width=corrected.width, height=corrected.height)

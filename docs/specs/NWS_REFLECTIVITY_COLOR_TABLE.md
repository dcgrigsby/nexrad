# NWS Reflectivity Color Table Specification

## Overview

The National Weather Service (NWS) uses a standardized color scale to represent radar reflectivity values (dBZ - decibels relative to Z). This scale maps dBZ intensity values to colors for visualization in weather radar displays. Higher dBZ values indicate stronger echoes and more intense precipitation.

## dBZ Intensity Scale

**dBZ (Decibels relative to Z)** represents the power of electromagnetic waves reflected back from precipitation:
- Higher values = stronger reflections = heavier precipitation
- Range: -30 dBZ to 75+ dBZ (practical range for weather radar)

## Standard NWS Color Mapping

The NWS standard reflectivity color scale follows this progression:

| dBZ Range | Color | Description | RGB |
|-----------|-------|-------------|-----|
| < -30 | No Data | Background (no echo) | (0, 0, 0) |
| -30 to -25 | Dark Gray | No precipitation | (100, 100, 100) |
| -25 to -20 | Light Gray | Clouds/no rain | (150, 150, 150) |
| -20 to -10 | Light Blue | Very weak returns | (65, 105, 225) |
| -10 to 0 | Cyan | Weak returns/drizzle | (0, 200, 255) |
| 0 to 5 | Light Cyan | Light rain | (50, 200, 255) |
| 5 to 10 | Blue | Light rain | (0, 150, 255) |
| 10 to 15 | Green | Light-moderate rain | (0, 200, 0) |
| 15 to 20 | Lime Green | Moderate rain | (100, 255, 0) |
| 20 to 25 | Yellow | Moderate rain | (255, 255, 0) |
| 25 to 30 | Orange | Moderate-heavy rain | (255, 165, 0) |
| 30 to 35 | Red Orange | Heavy rain | (255, 100, 0) |
| 35 to 40 | Red | Heavy rain | (255, 0, 0) |
| 40 to 45 | Dark Red | Very heavy rain | (180, 0, 0) |
| 45 to 50 | Magenta | Extreme rain | (255, 0, 255) |
| 50 to 55 | Violet | Extreme rain/hail | (138, 43, 226) |
| 55 to 60 | White | Extreme rain/hail | (255, 255, 255) |
| 60 to 75 | Bright White | Extreme rain/hail/debris | (255, 255, 255) |
| 75+ | Bright White | Extreme/debris | (255, 255, 255) |

## Color Progression Characteristics

### Light Precipitation (0-20 dBZ)
- **Colors**: Blues and greens
- **Interpretation**: Light to moderate rain
- **dBZ meaning**: Reflectivity ≥ 20 dBZ indicates the start of typical rain rates

### Moderate Precipitation (20-35 dBZ)
- **Colors**: Yellow, orange, red
- **Interpretation**: Moderate to heavy rainfall
- **dBZ meaning**: 30 dBZ ≈ 1 inch/hour rain rate

### Heavy Precipitation (35-50 dBZ)
- **Colors**: Dark red, magenta, violet
- **Interpretation**: Heavy rain and possible hail
- **dBZ meaning**: 40 dBZ ≈ 2-3 inches/hour rain rate

### Extreme Precipitation (50+ dBZ)
- **Colors**: White, bright white
- **Interpretation**: Extreme rainfall, hail, or radar-reflective debris
- **dBZ meaning**: 50+ dBZ indicates severe weather potential

## Alternative NWS Color Schemes

The NWS has published multiple standardized color tables over time. The most common modern version is shown above, but variants exist:

### Classic NWS Color Table (older standard)
Some legacy systems use slightly different color boundaries and RGB values. Key differences:
- Earlier boundaries at different thresholds (e.g., 10, 25, 40, 50 instead of more granular steps)
- Slightly different RGB values for intermediate colors
- Fewer color steps (8-12 colors instead of 16-18)

## Practical Implementation Notes

### RGB Value Specification
- Each color component: 0-255 (8-bit unsigned integer)
- Format: (Red, Green, Blue)
- Examples:
  - Pure red: (255, 0, 0)
  - Pure green: (0, 255, 0)
  - Pure blue: (0, 0, 255)
  - White: (255, 255, 255)
  - Black: (0, 0, 0)

### Interpolation
When exact dBZ value falls between defined thresholds:
- Use nearest-neighbor approach (pick the range it falls in)
- OR use linear RGB interpolation between adjacent color boundaries

### Display Considerations
- Modern displays use sRGB color space
- Reflectivity displays often use logarithmic scaling to enhance detail in weak echo regions
- Transparency/alpha channel sometimes used for missing data regions

## References

- National Weather Service Radar Operations Center (ROC)
- NOAA National Centers for Environmental Prediction (NCEP)
- Standard NWS WSR-88D (Next Generation Radar) documentation
- Color scales have evolved; this represents current standard as of 2024-2025

## Related Standards

- **dBZ to Rain Rate Conversion**:
  - Marshall-Palmer relationship: Z = 200*R^1.6
  - Where Z is reflectivity (dBZ), R is rain rate (mm/hr)

- **Hail Indicators**:
  - dBZ > 50 indicates possible hail
  - Vertically integrated reflectivity (VIL) > 30 is severe hail indicator

- **Severe Weather Thresholds**:
  - Reflectivity > 50 dBZ: Severe rain/hail threat
  - Reflectivity > 60 dBZ: Extreme precipitation/debris

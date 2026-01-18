# Q-LidarLink

Because apparently dragging a 3D scan into QGIS and having it appear in the right continent was too much to ask.

## What is this?

A Python script that loads mobile LiDAR scans (Polycam, SiteScape, etc.) into QGIS and actually puts them where the GPS said they were. Revolutionary stuff.

## The Problem

You scan an excavation with your fancy iPhone. Export the GLB. Import into QGIS. Model appears at coordinates (0, 0, 0) somewhere in the Atlantic Ocean off the coast of Africa. You spend the next 3 hours in CloudCompare trying to figure out rotation matrices. 

We've all been there. Well, I have. Multiple times. Hence this script.

## Requirements

- QGIS 3.40+ (for the `native:gltftovector` algorithm that does the actual hard work)
- Python 3 (comes with QGIS, you're welcome)
- A mobile LiDAR scan that you'd like to see in its actual geographic location

## Usage

Open QGIS Python Console (`Ctrl+Alt+P`) and type:

```python
import sys
sys.path.insert(0, '/path/to/Q-LidarLink')
from lidar_link import load_scan

# Option A: You know where this thing should go
layer = load_scan(
    mesh_path='/path/to/excavation.glb',
    latitude=39.4699,
    longitude=-0.3763,
    altitude=10,
    heading=45  # Rotate 45 degrees from north if needed
)

# Option B: Let the script read Polycam's metadata (even from ZIP)
from lidar_link import load_from_export
layer = load_from_export('/path/to/polycam_export.zip')
```

Then open View > 3D Map View and witness your model appear roughly where you scanned it.

## Features

- **Automatic geolocation**: WGS84 to project CRS transformation
- **Rotation support**: Applies heading/pitch/roll from ARKit quaternions
- **ZIP extraction**: Reads directly from Polycam ZIP exports
- **Metadata parsing**: Auto-detects Polycam and SiteScape formats
- **Performance warnings**: Tells you when your mesh is too big (spoiler: it probably is)

## Does it work?

Yes, with caveats:

1. GPS accuracy on mobile devices is what it is. If your scan appears 5 meters off, that's not a bug, that's your phone lying to you.

2. If your mesh has 500k polygons, QGIS will choke. Decimate in Meshlab/Blender first. Aim for < 50k polygons. The script will warn you, but it won't stop you from freezing QGIS.

3. The Y-up to Z-up conversion math was written at 2am. It works in my tests. Your mileage may vary.

## Project Structure

```
Q-LidarLink/
├── lidar_link.py        # The main script you'll actually use
├── geo_transform.py     # Coordinate and rotation math
├── rotation_utils.py    # Quaternions to Euler (the fun part)
├── metadata_parser.py   # Reads those JSON files Polycam exports
└── sample_data/         # Test files for when you don't have a real scan
```

## Roadmap

- [x] Basic coordinate transformation
- [x] Polycam metadata parser
- [x] Automatic ZIP extraction
- [x] Rotation from ARKit quaternions
- [ ] Scale transformation
- [ ] Full QGIS plugin with buttons and dialogs
- [ ] World peace

## Contributing

If you find a bug, you probably know more about this than I do. Pull requests welcome.

## License

MIT. Do whatever you want with it. If you use it in a publication, a citation would be nice but I won't track you down.

---

*Made for archaeologists who just want their iPhone scans to show up in the right place.*

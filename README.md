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
    altitude=10
)

# Option B: Let the script read Polycam's metadata
from lidar_link import load_from_export
layer = load_from_export('/path/to/polycam_export/')
```

Then open View > 3D Map View and witness your model appear roughly where you scanned it.

## Does it work?

In theory, yes. In practice, GPS accuracy on mobile devices is what it is. If your scan appears 5 meters off, that's not a bug, that's your phone lying to you.

## Project Structure

```
Q-LidarLink/
├── lidar_link.py        # The main script you'll actually use
├── geo_transform.py     # Coordinate math that I had to look up
├── rotation_utils.py    # Quaternions. Don't ask.
├── metadata_parser.py   # Reads those JSON files Polycam exports
└── sample_data/         # Test files for when you don't have a real scan
```

## Roadmap

- [x] Basic coordinate transformation
- [x] Polycam metadata parser
- [ ] Automatic ZIP extraction (currently you have to unzip yourself, sorry)
- [ ] Rotation from ARKit quaternions (because Y-up vs Z-up is a thing)
- [ ] Full QGIS plugin with buttons and dialogs
- [ ] World peace

## Contributing

If you find a bug, you probably know more about this than I do. Pull requests welcome.

## License

MIT. Do whatever you want with it. If you use it in a publication, a citation would be nice but I won't track you down.

---

*Made for archaeologists who just want their iPhone scans to show up in the right place.*
# Q-LidarLink

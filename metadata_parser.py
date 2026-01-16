"""
metadata_parser.py - Mobile Scan Metadata Parser for Q-LidarLink

Parses export files from Polycam, SiteScape, and other mobile LiDAR apps.
"""

import json
import zipfile
import os
from pathlib import Path
from typing import Dict, Any, Optional, Tuple


class ScanMetadata:
    """Container for parsed scan metadata."""
    
    def __init__(self):
        self.latitude: float = 0.0
        self.longitude: float = 0.0
        self.altitude: float = 0.0
        self.quaternion: Tuple[float, float, float, float] = (0, 0, 0, 1)  # (x, y, z, w)
        self.alignment_transform: Optional[list] = None  # 4x4 matrix if available
        self.mesh_path: Optional[str] = None
        self.source_app: str = "unknown"
        self.raw_metadata: Dict[str, Any] = {}
    
    def has_geolocation(self) -> bool:
        """Check if valid GPS coordinates are present."""
        return self.latitude != 0.0 or self.longitude != 0.0
    
    def has_rotation(self) -> bool:
        """Check if rotation data is present (non-identity quaternion)."""
        return self.quaternion != (0, 0, 0, 1)
    
    def __repr__(self):
        return (f"ScanMetadata(lat={self.latitude:.6f}, lon={self.longitude:.6f}, "
                f"alt={self.altitude:.1f}m, source={self.source_app})")


def parse_polycam_export(path: str) -> ScanMetadata:
    """
    Parse a Polycam raw export (ZIP file or extracted folder).
    
    Polycam raw exports contain:
        - mesh_info.json: Mesh metadata with georeference and alignment
        - cameras.json: Camera poses in ARKit coordinates
        - raw.glb: The 3D mesh
        
    Args:
        path: Path to .zip file or extracted folder
        
    Returns:
        ScanMetadata object with parsed information
    """
    metadata = ScanMetadata()
    metadata.source_app = "polycam"
    
    # Determine if path is zip or folder
    if path.endswith('.zip'):
        return _parse_polycam_zip(path)
    else:
        return _parse_polycam_folder(path)


def _parse_polycam_folder(folder_path: str) -> ScanMetadata:
    """Parse extracted Polycam folder."""
    metadata = ScanMetadata()
    metadata.source_app = "polycam"
    folder = Path(folder_path)
    
    # Look for mesh_info.json
    mesh_info_path = folder / "mesh_info.json"
    if mesh_info_path.exists():
        with open(mesh_info_path, 'r') as f:
            mesh_info = json.load(f)
            metadata.raw_metadata['mesh_info'] = mesh_info
            _extract_polycam_georeference(mesh_info, metadata)
    
    # Look for cameras.json (for rotation data)
    cameras_path = folder / "cameras.json"
    if cameras_path.exists():
        with open(cameras_path, 'r') as f:
            cameras = json.load(f)
            metadata.raw_metadata['cameras'] = cameras
            _extract_polycam_orientation(cameras, metadata)
    
    # Find mesh file
    for mesh_name in ['raw.glb', 'mesh.glb', 'model.glb', 'raw.obj', 'mesh.obj']:
        mesh_path = folder / mesh_name
        if mesh_path.exists():
            metadata.mesh_path = str(mesh_path)
            break
    
    return metadata


def _parse_polycam_zip(zip_path: str) -> ScanMetadata:
    """Parse Polycam ZIP export."""
    metadata = ScanMetadata()
    metadata.source_app = "polycam"
    
    with zipfile.ZipFile(zip_path, 'r') as zf:
        # List files in zip
        file_list = zf.namelist()
        
        # Find and parse mesh_info.json
        mesh_info_files = [f for f in file_list if f.endswith('mesh_info.json')]
        if mesh_info_files:
            with zf.open(mesh_info_files[0]) as f:
                mesh_info = json.load(f)
                metadata.raw_metadata['mesh_info'] = mesh_info
                _extract_polycam_georeference(mesh_info, metadata)
        
        # Find and parse cameras.json
        cameras_files = [f for f in file_list if f.endswith('cameras.json')]
        if cameras_files:
            with zf.open(cameras_files[0]) as f:
                cameras = json.load(f)
                metadata.raw_metadata['cameras'] = cameras
                _extract_polycam_orientation(cameras, metadata)
        
        # Find mesh file path (will need extraction for actual use)
        for f in file_list:
            if f.endswith(('.glb', '.gltf', '.obj', '.ply')):
                metadata.mesh_path = f  # Relative path within zip
                break
    
    return metadata


def _extract_polycam_georeference(mesh_info: dict, metadata: ScanMetadata):
    """Extract georeference data from Polycam mesh_info.json."""
    
    # Try different possible key structures
    # Polycam format may vary by version
    
    # Direct georeference keys
    if 'latitude' in mesh_info:
        metadata.latitude = float(mesh_info['latitude'])
    if 'longitude' in mesh_info:
        metadata.longitude = float(mesh_info['longitude'])
    if 'altitude' in mesh_info:
        metadata.altitude = float(mesh_info['altitude'])
    
    # Nested under 'georeference' key
    if 'georeference' in mesh_info:
        geo = mesh_info['georeference']
        metadata.latitude = float(geo.get('latitude', metadata.latitude))
        metadata.longitude = float(geo.get('longitude', metadata.longitude))
        metadata.altitude = float(geo.get('altitude', metadata.altitude))
    
    # Nested under 'location' key
    if 'location' in mesh_info:
        loc = mesh_info['location']
        metadata.latitude = float(loc.get('lat', loc.get('latitude', metadata.latitude)))
        metadata.longitude = float(loc.get('lon', loc.get('longitude', metadata.longitude)))
        metadata.altitude = float(loc.get('alt', loc.get('altitude', metadata.altitude)))
    
    # Alignment transform (4x4 matrix)
    if 'alignmentTransform' in mesh_info:
        metadata.alignment_transform = mesh_info['alignmentTransform']


def _extract_polycam_orientation(cameras: dict, metadata: ScanMetadata):
    """Extract initial orientation from Polycam cameras.json."""
    
    # Get first camera pose for initial orientation
    # Structure can vary: list of cameras or dict with 'frames'
    
    frames = None
    if isinstance(cameras, list) and len(cameras) > 0:
        frames = cameras
    elif isinstance(cameras, dict):
        frames = cameras.get('frames', cameras.get('cameras', []))
    
    if frames and len(frames) > 0:
        first_frame = frames[0]
        
        # Look for quaternion
        if 'quaternion' in first_frame:
            q = first_frame['quaternion']
            if isinstance(q, dict):
                metadata.quaternion = (
                    float(q.get('x', 0)),
                    float(q.get('y', 0)),
                    float(q.get('z', 0)),
                    float(q.get('w', 1))
                )
            elif isinstance(q, list) and len(q) >= 4:
                metadata.quaternion = (q[0], q[1], q[2], q[3])
        
        # Or extract from transform matrix
        elif 'transform' in first_frame:
            # Transform is typically a 4x4 matrix in row-major order
            # We could extract rotation, but quaternion is more reliable if present
            pass


def parse_sitescape_export(path: str) -> ScanMetadata:
    """
    Parse a SiteScape export.
    
    SiteScape exports typically include:
        - JSON metadata with GPS coordinates
        - PLY or OBJ mesh file
        
    Args:
        path: Path to export folder or file
        
    Returns:
        ScanMetadata object
    """
    metadata = ScanMetadata()
    metadata.source_app = "sitescape"
    
    folder = Path(path) if os.path.isdir(path) else Path(path).parent
    
    # Look for JSON metadata files
    for json_file in folder.glob('*.json'):
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                metadata.raw_metadata[json_file.name] = data
                
                # Extract location if present
                if 'location' in data:
                    loc = data['location']
                    metadata.latitude = float(loc.get('latitude', 0))
                    metadata.longitude = float(loc.get('longitude', 0))
                    metadata.altitude = float(loc.get('altitude', 0))
                    break
        except (json.JSONDecodeError, KeyError):
            continue
    
    # Find mesh file
    for ext in ['.ply', '.obj', '.glb', '.gltf']:
        mesh_files = list(folder.glob(f'*{ext}'))
        if mesh_files:
            metadata.mesh_path = str(mesh_files[0])
            break
    
    return metadata


def auto_detect_and_parse(path: str) -> ScanMetadata:
    """
    Auto-detect export source and parse accordingly.
    
    Args:
        path: Path to export file or folder
        
    Returns:
        ScanMetadata object
    """
    path_obj = Path(path)
    
    # Check for Polycam indicators
    if path.endswith('.zip'):
        with zipfile.ZipFile(path, 'r') as zf:
            files = zf.namelist()
            if any('polycam' in f.lower() or 'mesh_info.json' in f for f in files):
                return parse_polycam_export(path)
    
    if path_obj.is_dir():
        # Check for Polycam structure
        if (path_obj / 'mesh_info.json').exists() or (path_obj / 'raw.glb').exists():
            return parse_polycam_export(path)
        
        # Default to SiteScape-style parsing
        return parse_sitescape_export(path)
    
    # Single file - create minimal metadata
    metadata = ScanMetadata()
    metadata.mesh_path = path
    metadata.source_app = "unknown"
    return metadata


def create_sample_metadata() -> dict:
    """
    Create sample Polycam-style metadata for testing.
    
    Returns:
        dict: Sample mesh_info.json structure
    """
    return {
        "version": "1.0",
        "latitude": 39.4699,
        "longitude": -0.3763,
        "altitude": 15.0,
        "alignmentTransform": [
            1, 0, 0, 0,
            0, 1, 0, 0,
            0, 0, 1, 0,
            0, 0, 0, 1
        ],
        "meshFile": "raw.glb",
        "captureDate": "2026-01-15T12:00:00Z"
    }

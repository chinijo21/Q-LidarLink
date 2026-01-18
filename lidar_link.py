"""
lidar_link.py - Main Entry Point for Q-LidarLink

Load mobile LiDAR scans (GLB/OBJ/PLY) into QGIS with automatic geolocation.

Usage in QGIS Python Console:
    
    # Add to path (run once)
    import sys
    sys.path.insert(0, '/mnt/storage/UV/GNU/Q-LidarLink')
    
    # Load a scan with manual coordinates
    from lidar_link import load_scan
    layer = load_scan(
        glb_path='/path/to/scan.glb',
        latitude=39.4699,
        longitude=-0.3763,
        altitude=10
    )
    
    # Load from Polycam export (auto-parse metadata)
    from lidar_link import load_from_export
    layer = load_from_export('/path/to/polycam_export.zip')
"""

import os
import zipfile
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Tuple

from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsCoordinateReferenceSystem,
    QgsPointXY,
    Qgis
)
from qgis import processing

# Local imports
from geo_transform import (wgs84_to_project_crs, apply_offset_to_layer, 
                           get_geometry_centroid_3d, apply_rotation_to_layer)
from rotation_utils import arkit_to_gis_rotation
from metadata_parser import auto_detect_and_parse, ScanMetadata


def load_scan(
    mesh_path: str,
    latitude: float,
    longitude: float,
    altitude: float = 0.0,
    heading: float = 0.0,
    pitch: float = 0.0,
    roll: float = 0.0,
    scale: float = 1.0,
    layer_name: Optional[str] = None
) -> Optional[QgsVectorLayer]:
    """
    Load a 3D mesh into QGIS at specified GPS coordinates.
    
    This is the core function for Q-LidarLink. It converts a GLB/GLTF mesh
    to QGIS vector features and positions them at the correct geographic location.
    
    Args:
        mesh_path: Path to .glb, .gltf, or .obj file
        latitude: WGS84 latitude in decimal degrees
        longitude: WGS84 longitude in decimal degrees
        altitude: Elevation in meters above sea level (default 0)
        heading: Rotation around Z-axis in degrees (0 = North, default 0)
        pitch: Rotation around X-axis in degrees (default 0)
        roll: Rotation around Y-axis in degrees (default 0)
        scale: Model scale factor (default 1.0)
        layer_name: Custom layer name (default: filename)
        
    Returns:
        QgsVectorLayer with 3D polygon geometry, or None on failure
        
    Example:
        >>> layer = load_scan(
        ...     mesh_path='/home/user/excavation.glb',
        ...     latitude=39.4699,
        ...     longitude=-0.3763,
        ...     altitude=10,
        ...     heading=45  # Rotated 45° from North
        ... )
    """
    mesh_path = str(Path(mesh_path).resolve())
    
    # Validate input file
    if not os.path.exists(mesh_path):
        print(f"❌ Error: File not found: {mesh_path}")
        return None
    
    supported_formats = ('.glb', '.gltf', '.obj')
    if not mesh_path.lower().endswith(supported_formats):
        print(f"❌ Error: Unsupported format. Use: {supported_formats}")
        return None
    
    # Check QGIS version for gltftovector support
    qgis_version = Qgis.versionInt()
    if qgis_version < 34000:
        print(f"⚠️ Warning: QGIS {Qgis.version()} may not support native:gltftovector.")
        print("   Consider upgrading to QGIS 3.40+")
    
    print(f"📂 Loading: {Path(mesh_path).name}")
    print(f"📍 Target coordinates: {latitude:.6f}°, {longitude:.6f}°, {altitude:.1f}m")
    
    # Step 1: Convert GLB to vector layer using QGIS processing
    try:
        result = processing.run("native:gltftovector", {
            'INPUT': mesh_path,
            'OUTPUT_POLYGONS': 'TEMPORARY_OUTPUT',
            'OUTPUT_LINES': 'TEMPORARY_OUTPUT'
        })
        
        polygon_layer = result.get('OUTPUT_POLYGONS')
        
        if polygon_layer is None or not polygon_layer.isValid():
            print("❌ Error: Failed to convert mesh to vector layer")
            return None
        
        poly_count = polygon_layer.featureCount()
        print(f"✓ Converted to {poly_count} polygons")
        
        # Performance warning for large meshes
        if poly_count > 50000:
            print(f"   ⚠️ WARNING: Large mesh ({poly_count} polygons)")
            print("   QGIS may be slow. Consider decimating the mesh before import.")
            print("   Tip: Use Meshlab or Blender to reduce polygon count to < 50k")
        
    except Exception as e:
        print(f"❌ Processing error: {e}")
        print("   Make sure QGIS 3.40+ is installed with native:gltftovector support")
        return None
    
    # Step 2: Get current centroid of the model (should be near origin)
    current_centroid = get_geometry_centroid_3d(polygon_layer)
    print(f"   Model centroid: ({current_centroid[0]:.2f}, {current_centroid[1]:.2f}, {current_centroid[2]:.2f})")
    
    # Step 3: Transform GPS coordinates to project CRS
    project_crs = QgsProject.instance().crs()
    if not project_crs.isValid():
        print("⚠️ Warning: No valid project CRS. Setting to EPSG:25830 (UTM 30N)")
        project_crs = QgsCoordinateReferenceSystem("EPSG:25830")
        QgsProject.instance().setCrs(project_crs)
    
    target_x, target_y, target_z = wgs84_to_project_crs(latitude, longitude, altitude)
    print(f"   Target in {project_crs.authid()}: ({target_x:.2f}, {target_y:.2f}, {target_z:.2f})")
    
    # Step 4: Calculate offset to move model from origin to target
    x_offset = target_x - current_centroid[0]
    y_offset = target_y - current_centroid[1]
    z_offset = target_z - current_centroid[2]
    
    # Step 5: Apply transformation
    print("   Applying transformation...")
    apply_offset_to_layer(polygon_layer, x_offset, y_offset, z_offset)
    
    # Step 6: Apply rotation if specified
    if heading != 0 or pitch != 0 or roll != 0:
        print(f"   Applying rotation: heading={heading:.1f}°, pitch={pitch:.1f}°, roll={roll:.1f}°")
        try:
            apply_rotation_to_layer(
                polygon_layer, 
                heading, pitch, roll,
                target_x, target_y, target_z
            )
            print("   ✓ Rotation applied")
        except Exception as e:
            print(f"   ⚠️ Rotation failed: {e}")
    
    # Step 7: Apply scale if not 1.0 (TODO: implement in future phase)
    if scale != 1.0:
        print(f"   ⚠️ Scale ({scale}x) - not yet implemented")
    
    # Step 8: Set layer name and add to project
    if layer_name is None:
        layer_name = Path(mesh_path).stem
    
    polygon_layer.setName(f"LiDAR_{layer_name}")
    polygon_layer.setCrs(project_crs)
    
    QgsProject.instance().addMapLayer(polygon_layer)
    
    print(f"✅ Layer added: '{polygon_layer.name()}'")
    print(f"   Open 3D View to visualize (View → 3D Map View)")
    
    return polygon_layer


def load_from_export(
    export_path: str,
    override_coordinates: Optional[Tuple[float, float, float]] = None,
    layer_name: Optional[str] = None
) -> Optional[QgsVectorLayer]:
    """
    Load a mobile scan from its export archive with auto-parsed metadata.
    
    Supports:
        - Polycam raw exports (.zip or extracted folder)
        - SiteScape exports
        
    Args:
        export_path: Path to .zip file or extracted export folder
        override_coordinates: Optional (lat, lon, alt) to override parsed GPS
        layer_name: Custom layer name
        
    Returns:
        QgsVectorLayer with georeferenced mesh
        
    Example:
        >>> layer = load_from_export('/path/to/polycam_export.zip')
        >>> # Or with coordinate override:
        >>> layer = load_from_export('/path/to/scan/', override_coordinates=(39.47, -0.38, 10))
    """
    print(f"🔍 Parsing export: {export_path}")
    
    # Parse metadata
    metadata = auto_detect_and_parse(export_path)
    print(f"   Detected source: {metadata.source_app}")
    
    # Check for mesh file
    if metadata.mesh_path is None:
        print("❌ Error: No mesh file found in export")
        return None
    
    # Handle mesh path (may be relative to export folder)
    mesh_path = metadata.mesh_path
    if not os.path.isabs(mesh_path):
        export_folder = Path(export_path)
        if export_folder.is_file() and export_path.lower().endswith('.zip'):
            # ZIP file - extract to temp directory
            print("   Extracting ZIP archive...")
            temp_dir = tempfile.mkdtemp(prefix='qlidarlink_')
            try:
                with zipfile.ZipFile(export_path, 'r') as zf:
                    zf.extractall(temp_dir)
                print(f"   ✓ Extracted to temporary folder")
                
                # Re-parse from extracted folder
                metadata = auto_detect_and_parse(temp_dir)
                if metadata.mesh_path:
                    mesh_path = str(Path(temp_dir) / metadata.mesh_path) if not os.path.isabs(metadata.mesh_path) else metadata.mesh_path
                else:
                    # Search for mesh files
                    for ext in ['*.glb', '*.gltf', '*.obj']:
                        found = list(Path(temp_dir).rglob(ext))
                        if found:
                            mesh_path = str(found[0])
                            break
            except zipfile.BadZipFile:
                print("❌ Error: Invalid ZIP file")
                return None
        else:
            mesh_path = str(export_folder / mesh_path)
    
    # Use override coordinates or parsed coordinates
    if override_coordinates:
        lat, lon, alt = override_coordinates
        print(f"   Using override coordinates: ({lat}, {lon}, {alt})")
    elif metadata.has_geolocation():
        lat, lon, alt = metadata.latitude, metadata.longitude, metadata.altitude
        print(f"   Parsed coordinates: ({lat:.6f}, {lon:.6f}, {alt:.1f}m)")
    else:
        print("❌ Error: No GPS coordinates in metadata and no override provided")
        return None
    
    # Get rotation from metadata
    heading, pitch, roll = 0.0, 0.0, 0.0
    if metadata.has_rotation():
        qx, qy, qz, qw = metadata.quaternion
        rx, ry, rz = arkit_to_gis_rotation(qx, qy, qz, qw)
        heading, pitch, roll = rz, rx, ry  # Map to heading/pitch/roll
        print(f"   Parsed rotation: heading={heading:.1f}°, pitch={pitch:.1f}°, roll={roll:.1f}°")
    
    # Load the scan
    return load_scan(
        mesh_path=mesh_path,
        latitude=lat,
        longitude=lon,
        altitude=alt,
        heading=heading,
        pitch=pitch,
        roll=roll,
        layer_name=layer_name
    )


def quick_test(latitude: float = 39.4699, longitude: float = -0.3763):
    """
    Quick test function to verify the setup works.
    
    Creates a simple test layer at the specified coordinates to verify
    coordinate transformation is working.
    
    Args:
        latitude: Test latitude (default: Valencia, Spain)
        longitude: Test longitude (default: Valencia, Spain)
    """
    from qgis.core import QgsFeature, QgsGeometry, QgsPoint
    
    print("🧪 Q-LidarLink Quick Test")
    print("=" * 40)
    
    # Check project CRS
    project_crs = QgsProject.instance().crs()
    print(f"Project CRS: {project_crs.authid() if project_crs.isValid() else 'NOT SET'}")
    
    # Test coordinate transformation
    target_x, target_y, target_z = wgs84_to_project_crs(latitude, longitude, 0)
    print(f"WGS84: ({latitude}, {longitude})")
    print(f"Transformed: ({target_x:.2f}, {target_y:.2f})")
    
    # Create a simple point layer at the target
    test_layer = QgsVectorLayer("PointZ?crs=" + project_crs.authid(), "Q-LidarLink_Test", "memory")
    
    provider = test_layer.dataProvider()
    feature = QgsFeature()
    point = QgsPoint(target_x, target_y, 10)  # 10m altitude
    feature.setGeometry(QgsGeometry(point))
    provider.addFeature(feature)
    test_layer.updateExtents()
    
    QgsProject.instance().addMapLayer(test_layer)
    
    print(f"✅ Test point added at target location")
    print(f"   Layer: 'Q-LidarLink_Test'")
    
    return test_layer


# Convenience message when imported
print("=" * 50)
print("  Q-LidarLink - Mobile LiDAR Integration for QGIS")
print("=" * 50)
print("\nAvailable functions:")
print("  load_scan(glb_path, lat, lon, alt)  - Load with manual coords")
print("  load_from_export(path)              - Auto-parse Polycam export")
print("  quick_test()                        - Verify setup works")
print("\nExample:")
print("  layer = load_scan('/path/to/scan.glb', 39.47, -0.38, 10)")
print()

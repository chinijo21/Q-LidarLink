"""
geo_transform.py - Coordinate Transformation Utilities for Q-LidarLink

Transforms WGS84 GPS coordinates to project CRS and applies offsets to layers.
"""

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
    QgsPointXY,
    QgsGeometry,
    QgsFeature,
    QgsVectorLayer
)


def wgs84_to_project_crs(lat: float, lon: float, alt: float = 0.0, 
                          target_crs: QgsCoordinateReferenceSystem = None) -> tuple:
    """
    Transform WGS84 (EPSG:4326) coordinates to target CRS.
    
    Args:
        lat: Latitude in decimal degrees
        lon: Longitude in decimal degrees  
        alt: Altitude in meters (default 0)
        target_crs: Target CRS. If None, uses current project CRS
        
    Returns:
        tuple: (x, y, z) in target CRS units (typically meters)
    """
    # Source CRS: WGS84
    source_crs = QgsCoordinateReferenceSystem("EPSG:4326")
    
    # Target CRS: use project CRS if not specified
    if target_crs is None:
        target_crs = QgsProject.instance().crs()
    
    if not target_crs.isValid():
        raise ValueError("Invalid target CRS. Set a valid project CRS or provide target_crs parameter.")
    
    # Create coordinate transform
    transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
    
    # Transform point (note: QgsPointXY takes x, y order = lon, lat)
    source_point = QgsPointXY(lon, lat)
    transformed_point = transform.transform(source_point)
    
    return (transformed_point.x(), transformed_point.y(), alt)


def project_crs_to_wgs84(x: float, y: float, z: float = 0.0,
                          source_crs: QgsCoordinateReferenceSystem = None) -> tuple:
    """
    Transform project CRS coordinates back to WGS84.
    
    Args:
        x, y: Coordinates in source CRS
        z: Altitude in meters (passed through unchanged)
        source_crs: Source CRS. If None, uses current project CRS
        
    Returns:
        tuple: (latitude, longitude, altitude)
    """
    target_crs = QgsCoordinateReferenceSystem("EPSG:4326")
    
    if source_crs is None:
        source_crs = QgsProject.instance().crs()
    
    if not source_crs.isValid():
        raise ValueError("Invalid source CRS.")
    
    transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
    source_point = QgsPointXY(x, y)
    transformed_point = transform.transform(source_point)
    
    # Return as lat, lon, alt
    return (transformed_point.y(), transformed_point.x(), z)


def apply_offset_to_layer(layer: QgsVectorLayer, 
                           x_offset: float, 
                           y_offset: float, 
                           z_offset: float = 0.0) -> QgsVectorLayer:
    """
    Shift all geometries in a layer by the specified offset.
    
    Args:
        layer: Input QgsVectorLayer with 3D geometry
        x_offset: X translation in layer CRS units
        y_offset: Y translation in layer CRS units
        z_offset: Z translation in layer CRS units
        
    Returns:
        Modified layer (in-place modification)
    """
    if not layer.isValid():
        raise ValueError("Invalid layer provided")
    
    layer.startEditing()
    
    for feature in layer.getFeatures():
        geom = feature.geometry()
        if geom.isNull():
            continue
            
        # Translate geometry
        geom.translate(x_offset, y_offset, z_offset)
        layer.changeGeometry(feature.id(), geom)
    
    layer.commitChanges()
    return layer


def get_geometry_centroid_3d(layer: QgsVectorLayer) -> tuple:
    """
    Calculate the 3D centroid of all geometries in a layer.
    
    Args:
        layer: QgsVectorLayer with geometry
        
    Returns:
        tuple: (x, y, z) centroid coordinates
    """
    x_sum, y_sum, z_sum = 0.0, 0.0, 0.0
    vertex_count = 0
    
    for feature in layer.getFeatures():
        geom = feature.geometry()
        if geom.isNull():
            continue
        
        # Get all vertices
        for vertex in geom.vertices():
            x_sum += vertex.x()
            y_sum += vertex.y()
            z_sum += vertex.z() if vertex.is3D() else 0.0
            vertex_count += 1
    
    if vertex_count == 0:
        return (0.0, 0.0, 0.0)
    
    return (x_sum / vertex_count, y_sum / vertex_count, z_sum / vertex_count)


def apply_rotation_to_layer(layer: QgsVectorLayer,
                             heading: float,
                             pitch: float,
                             roll: float,
                             center_x: float,
                             center_y: float,
                             center_z: float = 0.0) -> QgsVectorLayer:
    """
    Rotate all geometries in a layer around a center point.
    
    Uses heading/pitch/roll convention:
        - heading: rotation around Z-axis (yaw), 0 = North, clockwise positive
        - pitch: rotation around X-axis
        - roll: rotation around Y-axis
    
    Args:
        layer: Input QgsVectorLayer with 3D geometry
        heading: Z-axis rotation in degrees
        pitch: X-axis rotation in degrees
        roll: Y-axis rotation in degrees
        center_x, center_y, center_z: Center of rotation
        
    Returns:
        Modified layer (in-place modification)
    """
    import math
    
    if not layer.isValid():
        raise ValueError("Invalid layer provided")
    
    # Convert degrees to radians
    h = math.radians(-heading)  # Negate for clockwise convention
    p = math.radians(pitch)
    r = math.radians(roll)
    
    # Precompute rotation matrix (Z * Y * X order for heading/pitch/roll)
    ch, sh = math.cos(h), math.sin(h)
    cp, sp = math.cos(p), math.sin(p)
    cr, sr = math.cos(r), math.sin(r)
    
    # Combined rotation matrix
    r00 = ch * cr + sh * sp * sr
    r01 = -ch * sr + sh * sp * cr
    r02 = sh * cp
    r10 = cp * sr
    r11 = cp * cr
    r12 = -sp
    r20 = -sh * cr + ch * sp * sr
    r21 = sh * sr + ch * sp * cr
    r22 = ch * cp
    
    layer.startEditing()
    
    for feature in layer.getFeatures():
        geom = feature.geometry()
        if geom.isNull():
            continue
        
        # Get WKT, parse vertices, rotate, rebuild
        # For efficiency with large meshes, we work with the abstract geometry
        abstract_geom = geom.get()
        
        # Transform each vertex
        for i in range(abstract_geom.vertexCount()):
            for j in range(abstract_geom.ringCount(i) if hasattr(abstract_geom, 'ringCount') else 1):
                for k in range(abstract_geom.vertexCount(i, j) if hasattr(abstract_geom, 'vertexCount') else abstract_geom.vertexCount()):
                    try:
                        vertex_id = abstract_geom.vertexId(i, j, k) if hasattr(abstract_geom, 'vertexId') else k
                        pt = abstract_geom.vertexAt(vertex_id) if isinstance(vertex_id, int) else abstract_geom.vertexAt(k)
                    except:
                        continue
                    
                    # Translate to origin
                    px = pt.x() - center_x
                    py = pt.y() - center_y
                    pz = (pt.z() if pt.is3D() else 0.0) - center_z
                    
                    # Apply rotation
                    new_x = r00 * px + r01 * py + r02 * pz + center_x
                    new_y = r10 * px + r11 * py + r12 * pz + center_y
                    new_z = r20 * px + r21 * py + r22 * pz + center_z
                    
                    # Move vertex (simplified - direct geometry manipulation)
                    geom.moveVertex(new_x, new_y, new_z, k)
        
        layer.changeGeometry(feature.id(), geom)
    
    layer.commitChanges()
    return layer

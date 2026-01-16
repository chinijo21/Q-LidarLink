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

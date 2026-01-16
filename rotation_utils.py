"""
rotation_utils.py - 3D Rotation Utilities for Q-LidarLink

Handles quaternion to Euler conversion and ARKit (Y-up) to GIS (Z-up) transforms.

Note: If scipy is not available, provides fallback implementations.
"""

import math
from typing import Tuple

# Try to import scipy, provide fallback if not available
try:
    from scipy.spatial.transform import Rotation
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


def quaternion_to_euler(qx: float, qy: float, qz: float, qw: float) -> Tuple[float, float, float]:
    """
    Convert quaternion to Euler angles (roll, pitch, yaw) in degrees.
    
    Args:
        qx, qy, qz, qw: Quaternion components (x, y, z, w)
        
    Returns:
        tuple: (roll, pitch, yaw) in degrees
    """
    if HAS_SCIPY:
        # Use scipy for robust conversion
        r = Rotation.from_quat([qx, qy, qz, qw])
        euler = r.as_euler('xyz', degrees=True)
        return (euler[0], euler[1], euler[2])
    else:
        # Fallback: manual conversion
        return _quaternion_to_euler_manual(qx, qy, qz, qw)


def _quaternion_to_euler_manual(qx: float, qy: float, qz: float, qw: float) -> Tuple[float, float, float]:
    """
    Manual quaternion to Euler conversion (fallback when scipy unavailable).
    
    Uses standard aerospace convention (Z-Y-X rotation order).
    """
    # Roll (x-axis rotation)
    sinr_cosp = 2 * (qw * qx + qy * qz)
    cosr_cosp = 1 - 2 * (qx * qx + qy * qy)
    roll = math.atan2(sinr_cosp, cosr_cosp)
    
    # Pitch (y-axis rotation)
    sinp = 2 * (qw * qy - qz * qx)
    if abs(sinp) >= 1:
        pitch = math.copysign(math.pi / 2, sinp)  # Use 90 degrees if out of range
    else:
        pitch = math.asin(sinp)
    
    # Yaw (z-axis rotation)
    siny_cosp = 2 * (qw * qz + qx * qy)
    cosy_cosp = 1 - 2 * (qy * qy + qz * qz)
    yaw = math.atan2(siny_cosp, cosy_cosp)
    
    # Convert to degrees
    return (
        math.degrees(roll),
        math.degrees(pitch),
        math.degrees(yaw)
    )


def arkit_to_gis_rotation(qx: float, qy: float, qz: float, qw: float) -> Tuple[float, float, float]:
    """
    Convert ARKit quaternion (Y-up) to GIS Euler angles (Z-up).
    
    ARKit coordinate system:
        - +X: Right
        - +Y: Up (gravity-aligned)
        - -Z: Camera forward direction
        
    GIS (QGIS 3D) coordinate system:
        - +X: East
        - +Y: North  
        - +Z: Up
        
    This function applies the necessary axis swap before Euler conversion.
    
    Args:
        qx, qy, qz, qw: ARKit quaternion components
        
    Returns:
        tuple: (rx, ry, rz) rotation angles in degrees for QGIS 3D
    """
    if HAS_SCIPY:
        # Create rotation from ARKit quaternion
        r_arkit = Rotation.from_quat([qx, qy, qz, qw])
        
        # Axis swap matrix: ARKit Y-up to GIS Z-up
        # ARKit Y → GIS Z, ARKit Z → GIS -Y
        # This is a -90 degree rotation around X axis
        r_axis_swap = Rotation.from_euler('x', -90, degrees=True)
        
        # Combined rotation
        r_gis = r_axis_swap * r_arkit
        
        # Get Euler angles for QGIS 3D
        euler = r_gis.as_euler('xyz', degrees=True)
        return (euler[0], euler[1], euler[2])
    else:
        # Fallback: Apply manual axis swap
        # Swap Y and Z, negate new Y
        qx_gis = qx
        qy_gis = -qz  
        qz_gis = qy
        qw_gis = qw
        
        return _quaternion_to_euler_manual(qx_gis, qy_gis, qz_gis, qw_gis)


def euler_to_quaternion(roll: float, pitch: float, yaw: float) -> Tuple[float, float, float, float]:
    """
    Convert Euler angles (degrees) to quaternion.
    
    Args:
        roll, pitch, yaw: Rotation angles in degrees
        
    Returns:
        tuple: (qx, qy, qz, qw) quaternion components
    """
    if HAS_SCIPY:
        r = Rotation.from_euler('xyz', [roll, pitch, yaw], degrees=True)
        q = r.as_quat()
        return (q[0], q[1], q[2], q[3])
    else:
        # Manual conversion
        roll_rad = math.radians(roll) / 2
        pitch_rad = math.radians(pitch) / 2
        yaw_rad = math.radians(yaw) / 2
        
        cr, sr = math.cos(roll_rad), math.sin(roll_rad)
        cp, sp = math.cos(pitch_rad), math.sin(pitch_rad)
        cy, sy = math.cos(yaw_rad), math.sin(yaw_rad)
        
        qw = cr * cp * cy + sr * sp * sy
        qx = sr * cp * cy - cr * sp * sy
        qy = cr * sp * cy + sr * cp * sy
        qz = cr * cp * sy - sr * sp * cy
        
        return (qx, qy, qz, qw)


def create_rotation_matrix_3x3(rx: float, ry: float, rz: float) -> list:
    """
    Create a 3x3 rotation matrix from Euler angles.
    
    Args:
        rx, ry, rz: Rotation angles in degrees
        
    Returns:
        list: 3x3 rotation matrix as nested list [[r11,r12,r13], [r21,r22,r23], [r31,r32,r33]]
    """
    if HAS_SCIPY:
        r = Rotation.from_euler('xyz', [rx, ry, rz], degrees=True)
        return r.as_matrix().tolist()
    else:
        # Manual 3x3 rotation matrix
        rx_rad = math.radians(rx)
        ry_rad = math.radians(ry)
        rz_rad = math.radians(rz)
        
        cx, sx = math.cos(rx_rad), math.sin(rx_rad)
        cy, sy = math.cos(ry_rad), math.sin(ry_rad)
        cz, sz = math.cos(rz_rad), math.sin(rz_rad)
        
        # Combined rotation matrix (X * Y * Z order)
        return [
            [cy*cz, -cy*sz, sy],
            [cx*sz + sx*sy*cz, cx*cz - sx*sy*sz, -sx*cy],
            [sx*sz - cx*sy*cz, sx*cz + cx*sy*sz, cx*cy]
        ]


def apply_rotation_to_point(x: float, y: float, z: float,
                            rx: float, ry: float, rz: float,
                            center_x: float = 0, center_y: float = 0, center_z: float = 0) -> Tuple[float, float, float]:
    """
    Rotate a 3D point around a center point.
    
    Args:
        x, y, z: Point coordinates
        rx, ry, rz: Rotation angles in degrees
        center_x, center_y, center_z: Center of rotation
        
    Returns:
        tuple: (new_x, new_y, new_z) rotated coordinates
    """
    # Translate to origin
    px = x - center_x
    py = y - center_y
    pz = z - center_z
    
    # Get rotation matrix
    rot = create_rotation_matrix_3x3(rx, ry, rz)
    
    # Apply rotation
    new_x = rot[0][0]*px + rot[0][1]*py + rot[0][2]*pz
    new_y = rot[1][0]*px + rot[1][1]*py + rot[1][2]*pz
    new_z = rot[2][0]*px + rot[2][1]*py + rot[2][2]*pz
    
    # Translate back
    return (new_x + center_x, new_y + center_y, new_z + center_z)

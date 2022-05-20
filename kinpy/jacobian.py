from os import link
from typing import Any, List, Optional
import numpy as np

from . import transform


def calc_jacobian(serial_chain: Any, th: List[float], tool: transform.Transform = transform.Transform()) -> np.ndarray:
    ndof = len(th)
    j_fl = np.zeros((6, ndof))
    cur_transform = tool.matrix()

    cnt = 0
    for f in reversed(serial_chain._serial_frames):
        if f.joint.joint_type == "revolute":
            cnt += 1
            delta = np.dot(f.joint.axis, cur_transform[:3, :3])
            d = np.dot(np.cross(f.joint.axis, cur_transform[:3, 3]), cur_transform[:3, :3])
            j_fl[:, -cnt] = np.hstack((d, delta))
        elif f.joint.joint_type == "prismatic":
            cnt += 1
            j_fl[:3, -cnt] = np.dot(f.joint.axis, cur_transform[:3, :3])
        cur_frame_transform = f.get_transform(th[-cnt]).matrix()
        cur_transform = np.dot(cur_frame_transform, cur_transform)

    pose = serial_chain.forward_kinematics(th).matrix()
    rotation = pose[:3, :3]
    j_tr = np.zeros((6, 6))
    j_tr[:3, :3] = rotation
    j_tr[3:, 3:] = rotation
    j_w = np.dot(j_tr, j_fl)
    return j_w

def calc_jacobian_frames(serial_chain: Any, th: List[float], link_name: str, tool: transform.Transform = transform.Transform()) -> np.ndarray:
    ndof = len(th)
    j_fl = np.zeros((6, ndof))
    cur_transform = tool.matrix()

    # select first num_th movable joints
    serial_frames = []
    num_movable_joints = 0
    for serial_frame in serial_chain._serial_frames:
        serial_frames.append(serial_frame)
        if serial_frame.joint.joint_type != "fixed":
            num_movable_joints += 1

        if serial_frame.link.name == link_name:
            break # found first n joints
        
    cnt = len(th) - num_movable_joints # only first num_th joints
    for f in reversed(serial_frames):
        if f.joint.joint_type == "revolute":
            cnt += 1
            delta = np.dot(f.joint.axis, cur_transform[:3, :3])
            d = np.dot(np.cross(f.joint.axis, cur_transform[:3, 3]), cur_transform[:3, :3])
            j_fl[:, -cnt] = np.hstack((d, delta))
        elif f.joint.joint_type == "prismatic":
            cnt += 1
            j_fl[:3, -cnt] = np.dot(f.joint.axis, cur_transform[:3, :3])
        cur_frame_transform = f.get_transform(th[-cnt]).matrix()
        cur_transform = np.dot(cur_frame_transform, cur_transform)

    poses = serial_chain.forward_kinematics(th, end_only=False)
    pose = poses[link_name].matrix()

    rotation = pose[:3, :3]
    j_tr = np.zeros((6, 6))
    j_tr[:3, :3] = rotation
    j_tr[3:, 3:] = rotation
    j_w = np.dot(j_tr, j_fl)

    return j_w

def calc_jacobian_frames_fast(serial_chain: Any, th: List[float], link_name: str, tool: transform.Transform = transform.Transform()) -> np.ndarray:
    ndof = len(th)
    j_fl = np.zeros((6, ndof))
    cur_transform = tool.matrix()

    # select first num_th movable joints
    serial_frames = []
    num_movable_joints = 0
    for serial_frame in serial_chain._serial_frames:
        serial_frames.append(serial_frame)
        if serial_frame.joint.joint_type != "fixed":
            num_movable_joints += 1

        if serial_frame.link.name == link_name:
            break # found first n joints
        
    cnt = len(th) - num_movable_joints # only first num_th joints
    for f in reversed(serial_frames):
        if f.joint.joint_type == "revolute":
            cnt += 1
            delta = np.dot(f.joint.axis, cur_transform[:3, :3])
            d = np.dot(np.cross(f.joint.axis, cur_transform[:3, 3]), cur_transform[:3, :3])
            j_fl[:, -cnt] = np.hstack((d, delta))
        elif f.joint.joint_type == "prismatic":
            cnt += 1
            j_fl[:3, -cnt] = np.dot(f.joint.axis, cur_transform[:3, :3])
        cur_frame_transform = f.get_transform(th[-cnt]).matrix()
        cur_transform = cur_frame_transform @ cur_transform

    poses = serial_chain.forward_kinematics(th, end_only=False)
    pose = poses[link_name].matrix()

    rotation = pose[:3, :3]
    j_tr = np.zeros((6, 6))
    j_tr[:3, :3] = rotation
    j_tr[3:, 3:] = rotation
    j_w = np.dot(j_tr, j_fl)

    return j_w


def calc_jacobian_frames_batch(serial_chain: Any, thb: np.array, link_name: str, poseb: Optional[np.array] = None) -> np.ndarray:
    """
    Arguments
    ====
    thb: np.array (batch_size, state_dim) 
    poses: np.array (batch_size, 4, 4)
    """
    ndof = thb.shape[1]
    j_fl = np.zeros((thb.shape[0], 6, ndof))
    cur_transform = np.repeat(np.eye(4)[None], repeats=thb.shape[0], axis=0)

    # select first num_th movable joints
    serial_frames = []
    num_movable_joints = 0
    num_joint = 0
    for serial_frame in serial_chain._serial_frames:
        serial_frames.append(serial_frame)
        if serial_frame.joint.joint_type != "fixed":
            num_movable_joints += 1
        num_joint += 1

        if serial_frame.link.name == link_name:
            break # found first n joints
        
    cnt = ndof - num_movable_joints # only first num_th joints
    for f in reversed(serial_frames):
        if f.joint.joint_type == "revolute":
            cnt += 1
            delta = np.atleast_2d(f.joint.axis @ cur_transform[:, :3, :3])
            d = np.cross(f.joint.axis, cur_transform[:, :3, 3])
            d = np.atleast_2d((d[:, None] @ cur_transform[:, :3, :3]).squeeze())
            j_fl[:, :, -cnt] = np.hstack((d, delta))
        elif f.joint.joint_type == "prismatic":
            cnt += 1
            j_fl[:, :3, -cnt] = f.joint.axis @ cur_transform[:, :3, :3]
        cur_frame_transform = f.get_transform_matrizes(thb[:, -cnt])
        cur_transform = cur_frame_transform @ cur_transform

    if poseb is None:
        poses = serial_chain.forward_kinematics_batch(thb, end_only=False)
        poseb = poses[:, num_joint - 1]

    rotation = poseb[:, :3, :3]
    j_tr = np.zeros((thb.shape[0], 6, 6))
    j_tr[:, :3, :3] = rotation
    j_tr[:, 3:, 3:] = rotation
    j_w = j_tr @ j_fl

    return j_w

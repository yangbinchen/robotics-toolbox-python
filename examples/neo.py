#!/usr/bin/env python
"""
@author Jesse Haviland
"""

import roboticstoolbox as rtb
import spatialmath as sm
import numpy as np
import qpsolvers as qp
import time

# Launch the simulator Swift
env = rtb.backend.Swift()
env.launch()

# Create a Panda robot object
panda = rtb.models.Panda()

# Set joint angles to ready configuration
panda.q = [-0.5653, -0.1941, -1.2602, -0.7896, -2.3227, -0.3919, -2.5173]

# Make two obstacles with velocities
s0 = rtb.Shape.Sphere(
    radius=0.05,
    base=sm.SE3(0.45, 0.4, 0.3)
)
s0.v = [0.01, -0.2, 0, 0, 0, 0]

s1 = rtb.Shape.Sphere(
    radius=0.05,
    base=sm.SE3(0.1, 0.35, 0.65)
)
s1.v = [0, -0.2, 0, 0, 0, 0]

# Make a target
s2 = rtb.Shape.Sphere(
    radius=0.02,
    base=sm.SE3(0.6, -0.2, 0.0)
)

# Add the Panda and shapes to the simulator
env.add(panda)
env.add(s0)
env.add(s1)
env.add(s2)
time.sleep(1)

# Number of joint in the panda which we are controlling
n = 7

# Set the desired end-effector pose to the location of s2
Tep = panda.fkine()
Tep.A[:3, 3] = s2.base.t

arrived = False

while not arrived:

    # The pose of the Panda's end-effector
    Te = panda.fkine()

    # Transform from the end-effector to desired pose
    eTep = Te.inv() * Tep

    # Spatial error
    e = np.sum(np.abs(np.r_[eTep.t, eTep.rpy() * np.pi/180]))

    # Calulate the required end-effector spatial velocity for the robot
    # to approach the goal. Gain is set to 1.0
    v, arrived = rtb.p_servo(Te, Tep, 1.0)

    # Gain term (lambda) for control minimisation
    Y = 0.01

    # Quadratic component of objective function
    Q = np.eye(n + 6)

    # Joint velocity component of Q
    Q[:n, :n] *= Y

    # Slack component of Q
    Q[n:, n:] = (1 / e) * np.eye(6)

    # The equality contraints
    Aeq = np.c_[panda.jacobe(), np.eye(6)]
    beq = v.reshape((6,))

    # The inequality constraints for joint limit avoidance
    Ain = np.zeros((n + 6, n + 6))
    bin = np.zeros(n + 6)

    # The minimum angle (in radians) in which the joint is allowed to approach
    # to its limit
    ps = 0.05

    # The influence angle (in radians) in which the velocity damper
    # becomes active
    pi = 0.9

    # Form the joint limit velocity damper
    Ain[:n, :n], bin[:n] = panda.joint_velocity_damper(ps, pi, n)

    for link in links:
        if link.jtype == link.VARIABLE:
            j += 1
        for col in link.collision:
            obj = s0
            l_Ain, l_bin, ret, wTcp = link_calc(link, col, obj, q[:j])
            if ret < closest:
                closest = ret
                closest_obj = obj
                closest_p = wTcp

            if l_Ain is not None and l_bin is not None:
                if Ain is None:
                    Ain = l_Ain
                else:
                    Ain = np.r_[Ain, l_Ain]

                if bin is None:
                    bin = np.array(l_bin)
                else:
                    bin = np.r_[bin, l_bin]

    # Linear component of objective function: the manipulability Jacobian
    c = np.r_[-panda.jacobm().reshape((n,)), np.zeros(6)]

    # The lower and upper bounds on the joint velocity and slack variable
    lb = -np.r_[panda.qdlim[:n], 10 * np.ones(6)]
    ub = np.r_[panda.qdlim[:n], 10 * np.ones(6)]

    # Solve for the joint velocities dq
    qd = qp.solve_qp(Q, c, Ain, bin, Aeq, beq, lb=lb, ub=ub)

    # Apply the joint velocities to the Panda
    panda.qd[:n] = qd[:n]

    # Step the simulator by 50 ms
    env.step(50)
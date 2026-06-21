import rospy
import actionlib
from control_msgs.msg import FollowJointTrajectoryAction, FollowJointTrajectoryGoal
from trajectory_msgs.msg import JointTrajectoryPoint
from sensor_msgs.msg import JointState
from std_srvs.srv import Trigger


class ArmController:
    NED2_JOINT_LIMITS = [
        (-2.99, 2.99), (-1.83, 0.61), (-1.34, 1.57),
        (-2.09, 2.09), (-1.92, 1.92), (-2.53, 2.53),
    ]

    def __init__(self):
        self.tool_id = int(rospy.get_param('~tool_id', 31))
        self.move_speed = float(rospy.get_param('~safe_speed_factor', 1.0))
        self.min_duration = float(rospy.get_param('~min_duration', 1.5))
        self.default_move_duration = float(
            rospy.get_param('~default_move_duration', 3.0))
        self.pick_dwell = float(rospy.get_param('~pick_dwell_sec', 0.35))
        self.current_joints = None

        rospy.Subscriber('/joint_states', JointState, self._joint_cb, queue_size=1)
        self.traj = actionlib.SimpleActionClient(
            '/niryo_robot_follow_joint_trajectory_controller/follow_joint_trajectory',
            FollowJointTrajectoryAction)
        rospy.loginfo('Waiting for trajectory server...')
        if not self.traj.wait_for_server(timeout=rospy.Duration(10)):
            raise RuntimeError('Trajectory action server unavailable')

    @staticmethod
    def _action_succeeded(result, state, label):
        if state != actionlib.GoalStatus.SUCCEEDED:
            rospy.logerr('%s failed: action state=%s', label, state)
            return False
        if result is None:
            rospy.logerr('%s failed: empty result', label)
            return False
        error_code = getattr(result, 'error_code', 0)
        if error_code not in (0, None):
            rospy.logerr('%s failed: error_code=%s', label, error_code)
            return False
        return True

    def _joint_cb(self, msg):
        try:
            idx = [msg.name.index('joint_{}'.format(i)) for i in range(1, 7)]
            self.current_joints = [msg.position[i] for i in idx]
        except ValueError:
            if len(msg.position) >= 6:
                self.current_joints = list(msg.position[:6])

    def _wait_for_joints(self, timeout=5.0):
        deadline = rospy.Time.now() + rospy.Duration(timeout)
        rate = rospy.Rate(20)
        while not rospy.is_shutdown() and rospy.Time.now() < deadline:
            if self.current_joints is not None:
                return True
            rate.sleep()
        rospy.logwarn('No joint states after %.1fs', timeout)
        return False

    def _update_tool(self):
        try:
            rospy.wait_for_service('/niryo_robot/tools/update_tool', timeout=2.0)
            rospy.ServiceProxy('/niryo_robot/tools/update_tool', Trigger)()
        except rospy.ROSException:
            rospy.logwarn('update_tool unavailable; continuing')

    def _check_limits(self, joints, margin=0.02):
        for i, q in enumerate(joints):
            lo, hi = self.NED2_JOINT_LIMITS[i]
            if q < lo + margin or q > hi - margin:
                rospy.logerr('joint_%d=%.3f out of range', i + 1, q)
                return False
        return True

    def move_joints_blind(self, joints, label='move'):
        joints = list(joints)
        if not self._check_limits(joints):
            return False

        duration = self.default_move_duration
        if self.current_joints:
            diff = max(abs(joints[i] - self.current_joints[i]) for i in range(6))
            duration = max(diff / self.move_speed, self.min_duration)
            rospy.loginfo('%s (%.1fs, max diff %.2f): %s',
                          label, duration, diff, [round(j, 3) for j in joints])
        else:
            rospy.logwarn('%s: no joint states; using default duration', label)

        goal = FollowJointTrajectoryGoal()
        goal.trajectory.joint_names = [
            'joint_{}'.format(i) for i in range(1, 7)]
        pt = JointTrajectoryPoint()
        pt.positions = joints
        pt.time_from_start = rospy.Duration(duration)
        goal.trajectory.points = [pt]

        self.traj.send_goal(goal)
        self.traj.wait_for_result()
        return self._action_succeeded(
            self.traj.get_result(), self.traj.get_state(), label)

    def prepare(self):
        self._wait_for_joints()
        self._update_tool()
        self.vacuum(pull=False)
        rospy.sleep(0.2)

    def go_board_view(self, board_joints):
        try:
            rospy.wait_for_service('/tictactoe/go_observation', timeout=1.0)
            resp = rospy.ServiceProxy('/tictactoe/go_observation', Trigger)()
            if resp.success:
                rospy.loginfo('board view via tictactoe go_observation')
                return True
            rospy.logwarn('tictactoe go_observation failed: %s', resp.message)
        except (rospy.ROSException, rospy.ServiceException):
            pass
        return self.move_joints_blind(board_joints, 'board view')

    def vacuum(self, pull=True):
        try:
            from tools_interface.srv import ToolCommand
        except ImportError:
            rospy.logerr('tools_interface not available')
            return False

        if pull:
            params = dict(
                id=self.tool_id, position=0, speed=1000,
                hold_torque=0, max_torque=1000)
        else:
            params = dict(
                id=self.tool_id, position=10000, speed=10000,
                hold_torque=1000, max_torque=1000)

        srv_name = '/niryo_robot/tools/pull_air_vacuum_pump'
        try:
            rospy.wait_for_service(srv_name, timeout=3.0)
            proxy = rospy.ServiceProxy(srv_name, ToolCommand)
            proxy(**params)
            return True
        except rospy.ServiceException as exc:
            rospy.logerr('Vacuum failed: %s', exc)
            return False

    def pick_at(self, above_joints, pick_joints):
        if not self.move_joints_blind(above_joints, 'above pill'):
            return False
        if not self.move_joints_blind(pick_joints, 'pick pill'):
            return False
        if not self.vacuum(pull=True):
            return False
        rospy.sleep(self.pick_dwell)
        if not self.move_joints_blind(above_joints, 'lift pill'):
            return False
        return True

    def place_at(self, target_joints, retreat_joints):
        if not self.move_joints_blind(target_joints, 'patient box'):
            return False
        rospy.sleep(0.1)
        if not self.vacuum(pull=False):
            return False
        rospy.sleep(0.1)
        return self.move_joints_blind(retreat_joints, 'retreat to scan view')

    @staticmethod
    def fetch_pose_joints(name, timeout=10):
        from niryo_robot_poses_handlers.srv import GetPose
        rospy.wait_for_service('/niryo_robot_poses_handlers/get_pose', timeout)
        get_pose = rospy.ServiceProxy(
            '/niryo_robot_poses_handlers/get_pose', GetPose)
        resp = get_pose(name)
        joints = resp.pose.joints
        if not joints or len(joints) != 6:
            raise RuntimeError("Pose '{}' has no joints".format(name))
        return list(joints)

cmake_minimum_required(VERSION 3.0.2)
project(dosify)

find_package(catkin REQUIRED COMPONENTS
  rospy
  std_msgs
  std_srvs
  sensor_msgs
  geometry_msgs
  control_msgs
  trajectory_msgs
  niryo_robot_msgs
  niryo_robot_arm_commander
  niryo_robot_poses_handlers
  message_generation
)

# Install Python package
catkin_python_setup()


catkin_package(
  CATKIN_DEPENDS rospy std_msgs std_srvs sensor_msgs geometry_msgs control_msgs trajectory_msgs message_runtime
)

# Install scripts
catkin_install_python(PROGRAMS
  scripts/robot_control_node.py
  scripts/dispense_node.py
  scripts/print_patient_week.py
  scripts/demo_dispense.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

# Install launch and config
install(DIRECTORY launch/
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/launch
)

install(DIRECTORY config/
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/config
)

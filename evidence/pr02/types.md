# ПР02 — топики и типы

| Полное имя | Тип, подтверждённый CLI | Назначение |
| --- | --- | --- |
| `/turtle1/cmd_vel` | `geometry_msgs/msg/Twist` | Команды линейной и угловой скорости, которые принимает `/turtlesim` для `turtle1`. |
| `/turtle1/pose` | `turtlesim_msgs/msg/Pose` | Текущие координаты, ориентация и скорости черепахи; тип получен через `ros2 topic type /turtle1/pose` в ROS 2 Lyrical. |
| `/cmd_vel` | `geometry_msgs/msg/Twist` во время ошибочной публикации | Другой топик без подписчика turtlesim; правильный тип не делает его эквивалентом `/turtle1/cmd_vel`. |

`ros2 interface show geometry_msgs/msg/Twist` показал два вложенных `Vector3`: `linear` и `angular`, у каждого есть поля `x`, `y`, `z` типа `float64`. В опыте `linear.x=1.0` задаёт поступательную скорость по направлению черепахи, `angular.z=0.5` задаёт поворот против часовой стрелки. Остальные поля не заданы и равны нулю. Исходный вывод команды: `twist-interface.txt`.

Сообщение позы имеет поля `x`, `y`, `theta`, `linear_velocity`, `angular_velocity`; их реальные значения до, во время сбоя и после исправления сохранены в `pose-*.txt` и `measurements.json`. Для Jazzy курс допускает другой тип `turtlesim/msg/Pose`; в этом опыте фактический вывод CLI — `turtlesim_msgs/msg/Pose`.

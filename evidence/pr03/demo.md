# ПР03 — первая нода: поза и команда

## Реализация

`src/patrol` — отдельный пакет `ament_python`; `turtle_bringup` из ПР02 сохранён.
Исполняемая команда `patrol` создаёт `/patrol`. Поле `subscription` хранит
подписку на `/turtle1/pose`; callback `on_pose` только сохраняет сообщение
в `last_pose`. Таймер с периодом 0,1 с вызывает `on_timer`, выбирающий команду
чистой функцией `command_from_pose` и публикующий её в относительный `cmd_vel`.
До первой позы все поля Twist равны нулю; после — `linear.x=0.5`,
`angular.z=0.3`, остальные поля нулевые. Тесты проверяют оба состояния,
неизменность входной позы и независимость возвращаемых сообщений.

Локально используется ROS 2 Lyrical и `turtlesim_msgs/msg/Pose`.
Для Jazzy предусмотрен `turtlesim/msg/Pose`; зависимости в `package.xml`
выбираются по `ROS_DISTRO`. CI использует Jazzy, его удалённый запуск
в этой сессии не подтверждён.

## Повторить с окном

В двух Bash-терминалах подключить ROS и workspace:

```bash
cd /home/reev/Desktop/ROS2
source /opt/ros/lyrical/setup.bash
source install/setup.bash
export ROS_DOMAIN_ID=18 # домен должен быть свободен
```

В A запустить `ros2 launch turtle_bringup sim.launch.py`.
В B сначала проверить исправный запуск:

```bash
ros2 run patrol patrol --ros-args -r cmd_vel:=/turtle1/cmd_vel
```

Черепаха движется. Остановить patrol через Ctrl+C и подождать 1,5 с.
Затем воспроизвести дефект без remap:

```bash
ros2 run patrol patrol
```

В третьем терминале с тем же окружением:

```bash
ros2 node info /patrol
ros2 topic info /cmd_vel --verbose
ros2 topic info /turtle1/cmd_vel --verbose
ros2 topic echo /cmd_vel geometry_msgs/msg/Twist --once
ros2 topic echo /turtle1/pose --once
```

У `/patrol` есть подписка на позу и ненулевые команды, но `/cmd_vel`
имеет 1 издателя и 0 подписчиков. На `/turtle1/cmd_vel` — 0 издателей
и 1 подписчик `/turtlesim`. Совпадение типа Twist не связывает разные имена.
В корневом namespace относительное `cmd_vel` разрешается в `/cmd_vel`.

Остановить patrol, затем запустить с тем же remap, что в исправном запуске.
Повторить наблюдения и измерить частоту:

```bash
ros2 topic info /turtle1/cmd_vel --verbose
ros2 topic echo /turtle1/cmd_vel geometry_msgs/msg/Twist --once
ros2 topic hz /turtle1/cmd_vel
```

Дать измерению работать 15 секунд, затем остановить только `hz`.
Remap меняет имя издателя без правок функции и связывает его с turtlesim.
Остановить patrol через Ctrl+C, подождать 1,5 с и проверить позу:
обе скорости должны стать нулевыми. Завершить launch через Ctrl+C.

## Жизненный цикл

`rclpy.init` создаёт контекст ROS, после чего конструктор ноды создаёт
издатель, подписку и таймер. `spin` обслуживает готовые события: получение
позы вызывает callback подписки, срабатывание таймера — callback публикации.
Callback не содержит цикла движения или ожидания, поэтому не блокирует executor.
Ctrl+C прекращает spin; `finally` уничтожает ноду и завершает контекст,
если он ещё действует. Исчезновение издателя не отправляет мгновенную
команду торможения: turtlesim останавливается по таймауту последней команды.
Поэтому скорость проверяется после ожидания, пока симулятор ещё работает.

## Автоматическое выполнение

`scripts/run_pr03.py` запускает настоящие ROS-ноды с
`QT_QPA_PLATFORM=offscreen` в свободном домене 18. Сохранены исходные выводы
CLI, команды с кодами возврата, частота и реальные координаты.
Это опыт агента, а не подтверждение ручной демонстрации студентом.
На защите необходимо повторить запуск с окном и объяснить результат.

Фактический результат: частота 10.000 Гц, процесс измерения
работал 15.365 с (исходное окно см. `cmd-hz.txt`).
Без remap смещение 0.000000; после remap расстояние
между двумя наблюдаемыми позициями 1.366481 единицы.
Это расстояние между точками, а не длина пройденной дуги.
После ожидания 1.5 с скорости равны нулю.
`nodes-final.txt` пуст: созданные ноды остановлены.

Сборка: `build.txt`; три успешных теста: `tests.txt`.
Имена и endpoints: `patrol-info.txt`, `info-broken.txt`,
`info-correct-during-broken.txt`, `info-fixed.txt`.
Команды: `command-broken.txt`, `command-fixed.txt`.
Числа: `measurements.json`; полный список выполненных команд: `commands.json`.

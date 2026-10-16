# ПР04 — параметры движения

## Реализация

Продолжен пакет `patrol` из ПР03: прежние подписка, таймер и публикация Twist
сохранены. До получения позы команда нулевая. После получения позы скорости
берутся из активной конфигурации.

| Параметр | По умолчанию | Допустимые значения |
| --- | --- | --- |
| `linear_speed` | 0.5 | Конечное число от 0 до 1 |
| `turn_rate` | 0.3 | Конечное число от −1 до 1 |
| `publish_hz` | 10.0 | Конечное число от 1 до 30 |

`updated_settings` создаёт новую конфигурацию и проверяет все её поля,
не меняя исходную. Проверка выполняется также при старте с переопределёнными
параметрами. `add_on_set_parameters_callback` только проверяет запрос;
`add_post_set_parameters_callback` применяет уже принятые значения.
Поэтому отказ другого callback тоже не меняет активные настройки.
При смене частоты прежний таймер отменяется и уничтожается, после чего
создаётся один таймер с периодом `1/publish_hz`. Используется обычный
однопоточный spin: callback таймера не выполняется параллельно обновлению.
Зависимость `rcl_interfaces` явно указана в `package.xml`.

## Сборка и тесты

```bash
source /opt/ros/lyrical/setup.bash
colcon build --symlink-install --packages-select turtle_bringup patrol
source install/setup.bash
ROS_DOMAIN_ID=19 python3 -m pytest src/patrol/test
```

Выводы сохранены в `build.txt` и `tests.txt`. Проверены переход 10→5 Гц,
ноль, отрицательная частота, NaN, бесконечность, обе границы диапазонов,
изменение команд и отклонение смешанного набора параметров целиком.
Тесты с настоящим объектом ноды проверяют единственный оставшийся таймер,
период 0,2 с, сохранение таймера и активных параметров при отказе.

## Ручной запуск

В терминалах A, B и C подключить ROS и workspace, выбрать один свободный домен:

```bash
cd /home/reev/Desktop/ROS2
source /opt/ros/lyrical/setup.bash
source install/setup.bash
export ROS_DOMAIN_ID=19
```

В A: `ros2 launch turtle_bringup sim.launch.py`.
В B: `ros2 run patrol patrol --ros-args -r cmd_vel:=/turtle1/cmd_vel`.
В C выполнить команды ниже. Каждое измерение `hz` оставить работать 15 секунд,
затем остановить только его через Ctrl+C; patrol продолжает работать.

```bash
ros2 topic type /turtle1/pose
ros2 param dump /patrol
ros2 topic hz /turtle1/cmd_vel
ros2 param set /patrol publish_hz 0.0
ros2 param get /patrol publish_hz
ros2 topic hz /turtle1/cmd_vel
ros2 param set /patrol publish_hz 5.0
ros2 topic hz /turtle1/cmd_vel
ros2 param set /patrol linear_speed 0.2
ros2 param set /patrol turn_rate -0.4
ros2 topic echo /turtle1/cmd_vel geometry_msgs/msg/Twist --once
ros2 param dump /patrol
ros2 service call /clear std_srvs/srv/Empty '{}'
ros2 action list -t
```

После отклонения нуля `get` должен вернуть 10.0, а поток остаться около
10 Гц. После принятия 5.0 поток должен стать около 5 Гц, без перезапуска
ноды. Последний Twist должен содержать `linear.x=0.2`, `angular.z=-0.4`.
В конце остановить patrol, подождать 1,5 с и убедиться в нулевых скоростях
по `/turtle1/pose`; затем остановить launch. Завершение процесса не означает
мгновенной отправки нулевого Twist: остановку обеспечивает таймаут turtlesim.

## Отдельный коммит с дефектом

Исправная реализация — `1e1d8e85f3f723634669c857f669db06eef5e0b9`.
Ветка `pr04-frequency-defect`, коммит
`6ef818013c4efdde0d8e1b8585390d7996b425b1`, отличается только пропуском
проверки `publish_hz`. Изменение сохранено также в `defect.patch`.
Основная ветка содержит исправную проверку.

Сначала проверен исправный запуск, затем дефект воспроизведён в отдельном
worktree. При том же `ros2 param set /patrol publish_hz 0.0` без проверки
код доходит до `1.0 / candidate.publish_hz`: нода прекращает работу с
`ZeroDivisionError: division by zero`. Это конкретный отказ, а не
предположение об отсутствии сообщений. Вывод CLI и его код завершения
записаны отдельно; главным доказательством служит traceback процесса ноды.

Повторить полный автоматический опыт, если ветка с дефектом доступна локально:

```bash
git worktree add --detach /tmp/pr04-defect-repeat 6ef818013c4efdde0d8e1b8585390d7996b425b1
ROS_DOMAIN_ID=19 python3 scripts/run_pr04.py --defect-checkout /tmp/pr04-defect-repeat
```

Если отдельная ветка не передана при клонировании, создать эквивалентную копию
из коммита реализации и применить сохранённый patch:

```bash
git worktree add --detach /tmp/pr04-defect-repeat 1e1d8e85f3f723634669c857f669db06eef5e0b9
git -C /tmp/pr04-defect-repeat apply /home/reev/Desktop/ROS2/evidence/pr04/defect.patch
ROS_DOMAIN_ID=19 python3 scripts/run_pr04.py --defect-checkout /tmp/pr04-defect-repeat
```

Скрипт загружает код дефектной ноды из выбранного checkout в отдельном процессе;
установленный пакет и основная рабочая копия остаются исправными. Повторный
запуск перезаписывает evidence, после него отчёт необходимо обновить.

## Сервис и действие

Запрос сервиса `/clear` получает один ответ после очистки следа.
Цель действия `/turtle1/rotate_absolute` задаёт длительное выполнение поворота;
протокол action поддерживает feedback, итоговый результат и отмену.
Собственные IDL и сервер action не добавлялись.

## Подтверждения опыта

Опыт выполнен агентом в ROS 2 Lyrical с настоящим turtlesim без окна
(`QT_QPA_PLATFORM=offscreen`), в свободном домене 19. Тип позы определён
командой CLI. Ручное повторение студентом и удалённый запуск CI в этой сессии
не подтверждены. CI настроен на Jazzy; локально проверен Lyrical.

Все выполненные команды, файлы вывода и коды возврата — в `commands.json`.

Фактические измерения, каждое с отдельным 15-секундным запуском `hz`:

| Состояние | Частота |
| --- | --- |
| Исходное | 10.000 Гц |
| После отклонения нуля | 10.000 Гц |
| После принятия 5.0 | 5.000 Гц |

Фрагменты фактического вывода CLI:

```text
$ ros2 param set /patrol publish_hz 0.0
Setting parameter failed: publish_hz must be finite and in [1.0, 30.0]
$ ros2 param get /patrol publish_hz
Double value is: 10.0
$ ros2 param set /patrol publish_hz 5.0
Set parameter successful
$ ros2 action list -t
/turtle1/rotate_absolute [turtlesim_msgs/action/RotateAbsolute]
```

В дефектной копии: `ZeroDivisionError: division by zero`, код процесса
1; код CLI после ожидания ответа —
124. Полный traceback — `patrol-defect.txt`.
После завершения исправной ноды и ожидания 1,5 с скорости нулевые;
`nodes-final.txt` пуст. Числа и коды сохранены в `measurements.json`.

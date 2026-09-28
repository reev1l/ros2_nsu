# ПР01 — фактический граф и доменный опыт

Дата опыта: 28 сентября 2026 года. Среда: нативная Ubuntu 26.04.1, ROS 2 Lyrical, `rmw_fastrtps_cpp`, `turtlesim` 1.10.9.

## Как получены результаты

Опыт выполнен агентом командой:

```bash
source /opt/ros/lyrical/setup.bash
python3 scripts/run_pr01.py
```

Скрипт запустил настоящий `turtlesim_node` с `QT_QPA_PLATFORM=offscreen` и настоящий `turtle_teleop_key` в псевдотерминале. Стрелка вверх передана байтами `ESC [ A`; движение подтверждено изменением опубликованных координат, а не наблюдением окна. Студент пока не выполнял ручную демонстрацию. Скрипт не создаёт собственных ROS-нод и не подменяет сообщения симулятора.

Перед опытом CLI с `--no-daemon --spin-time 2` проверил отсутствие нод в обоих доменах. Симулятор на всех стадиях оставался одним и тем же процессом в домене 16. Менялись только запускаемые процессы teleop и CLI-наблюдателя. Логи всех CLI-команд, домены, коды возврата и длительности находятся в [commands.json](commands.json), координаты и частота — в [measurements.json](measurements.json).

## Исправный граф

Запуск симулятора и управления в домене 16:

```bash
export ROS_DOMAIN_ID=16
QT_QPA_PLATFORM=offscreen ros2 run turtlesim turtlesim_node
# В другом терминале/PTY с тем же domain:
ros2 run turtlesim turtle_teleop_key
```

Команда `ros2 node list --no-daemon --spin-time 2` в домене 16 дала:

```text
/teleop_turtle
/turtlesim
```

- `/teleop_turtle` читает клавиатуру и публикует команды движения.
- `/turtlesim` подписывается на команды и публикует состояние черепахи.
- CLI-наблюдатели запускаются кратковременно. Скрытые служебные CLI-ноды не включены в обычный список нод.

Команда `ros2 topic list -t --no-daemon --spin-time 2` дала:

```text
/parameter_events [rcl_interfaces/msg/ParameterEvent]
/rosout [rcl_interfaces/msg/Log]
/turtle1/cmd_vel [geometry_msgs/msg/Twist]
/turtle1/color_sensor [turtlesim_msgs/msg/Color]
/turtle1/pose [turtlesim_msgs/msg/Pose]
```

Основные связи:

```text
/teleop_turtle -- /turtle1/cmd_vel (geometry_msgs/msg/Twist) --> /turtlesim
/turtlesim -- /turtle1/pose (turtlesim_msgs/msg/Pose) --> CLI-наблюдатель
/turtlesim -- /turtle1/color_sensor (turtlesim_msgs/msg/Color)
```

`ros2 node info /turtlesim --no-daemon --spin-time 2` подтвердил подписку на `/turtle1/cmd_vel` и публикацию `/turtle1/pose`, `/turtle1/color_sensor`, `/parameter_events`, `/rosout`. Полный вывод с сервисами и action сохранён в [turtlesim-info.txt](turtlesim-info.txt).

`ros2 node info /teleop_turtle --no-daemon --spin-time 2` подтвердил публикацию `/turtle1/cmd_vel`, `/parameter_events`, `/rosout`; полный вывод — в [teleop-info.txt](teleop-info.txt).

`ros2 topic type /turtle1/pose --no-daemon --spin-time 2` вернул:

```text
turtlesim_msgs/msg/Pose
```

Одно сообщение получено командой:

```bash
timeout 5s ros2 topic echo /turtle1/pose turtlesim_msgs/msg/Pose --once --no-daemon
```

Фактический начальный вывод ([pose-before.txt](pose-before.txt)), код возврата 0:

```yaml
x: 5.544444561004639
y: 5.544444561004639
theta: 0.0
linear_velocity: 0.0
angular_velocity: 0.0
---
```

После стрелки в teleop домена 16 координата x стала `7.560444355010986`; y не изменилась. Перемещение составило `2.0159997940063477` единицы координат симулятора. Источник — [pose-after-key-before.txt](pose-after-key-before.txt).

## Частота сообщений

Фактически выполненная команда:

```bash
ROS_DOMAIN_ID=16 timeout --signal=INT 15s ros2 topic hz /turtle1/pose
```

Команда работала 15 секунд, а затем `timeout` отправил SIGINT. Код 124 здесь означает запланированное окончание измерения, а не потерю сообщений. Получено 13 строк со средними частотами. Последняя:

```text
average rate: 62.497
    min: 0.015s max: 0.017s std dev: 0.00050s window: 811
```

Фактическая частота соответствует ориентиру задания 60–62,5 Гц. Черепаха во время измерения не двигалась, но поза продолжала публиковаться. Полный вывод — [pose-hz.txt](pose-hz.txt).

## Разрыв связи

Симулятор остаётся в домене 16. Teleop остановлен и запущен заново в 17:

```bash
export ROS_DOMAIN_ID=17
ros2 run turtlesim turtle_teleop_key
ros2 node list --no-daemon --spin-time 2
```

CLI-наблюдатель домена 17 увидел только:

```text
/teleop_turtle
```

Тип позы получен до разрыва и явно указан в команде. Поэтому отсутствие издателя не мешает CLI создать подписчика нужного типа:

```bash
ROS_DOMAIN_ID=17 timeout 5s ros2 topic echo /turtle1/pose turtlesim_msgs/msg/Pose --once --no-daemon
```

Поза не пришла; после 5 секунд код возврата — **124**. В [pose-broken.txt](pose-broken.txt) нет полей сообщения Pose; единственная строка — `!rclpy.ok()`, выведенная CLI при остановке по таймауту. Код записан отдельно в [pose-broken.txt.exit.txt](pose-broken.txt.exit.txt); это не ошибка импорта.

Стрелка отправлена teleop домена 17. Контрольное чтение позы через отдельный CLI домена 16 до и после стрелки показало одинаковые координаты: x = `7.560444355010986`, y = `5.544444561004639`. Перемещение — **0**. Эти дополнительные измерения не меняли домен teleop или симулятора и сохранены в `pose-observed-before-broken-key.txt` и `pose-observed-after-broken-key.txt`.

## Восстановление

Teleop остановлен и запущен заново в домене 16. Наблюдатель тоже использует 16:

```bash
export ROS_DOMAIN_ID=16
ros2 run turtlesim turtle_teleop_key
# В CLI-наблюдателе:
ros2 node list --no-daemon --spin-time 2
timeout 5s ros2 topic echo /turtle1/pose turtlesim_msgs/msg/Pose --once --no-daemon
```

Обе ноды обнаружены снова:

```text
/teleop_turtle
/turtlesim
```

Тот же тест echo, с изменением только домена, получил позу и завершился с кодом **0**. Сохранены [pose-fixed.txt](pose-fixed.txt) и [pose-fixed.txt.exit.txt](pose-fixed.txt.exit.txt).

После стрелки в восстановленном teleop координата x стала `9.576444625854492`, y осталась `5.544444561004639`. Перемещение — `2.016000270843506` единицы: управление восстановилось. Источник — [pose-after-key-fixed.txt](pose-after-key-fixed.txt).

| Стадия | Домен симулятора | Домен teleop / основного наблюдателя | Результат echo | Перемещение от стрелки |
| --- | --- | --- | --- | --- |
| До сбоя | 16 | 16 | Поза, код 0 | 2,016 |
| Сбой | 16 | 17 | Нет позы, код 124 | 0 |
| После исправления | 16 | 16 | Поза, код 0 | 2,016 |

## Причина и исправление

`ROS_DOMAIN_ID` задаёт область обнаружения DDS-участников при запуске. Участники доменов 16 и 17 не обнаруживают друг друга; совпадение имён топиков и типов сообщений этого не меняет. Teleop в 17 публикует команды, но симулятор в 16 их не получает. По той же причине подписчик в 17 не получает позу симулятора.

`export ROS_DOMAIN_ID=16` меняет окружение будущих процессов, а не уже работающую ноду. Поэтому для исправления teleop остановлен и запущен снова с нужным доменом. Симулятор уже находился в 16, менять или перезапускать его не потребовалось. Переустановка ROS не нужна: установка и типы сообщений были исправны.

После опыта созданные процессы остановлены. `node list --no-daemon --spin-time 2` подтвердил отсутствие нод в обоих доменах; результаты — `nodes-cleanup-16.txt` и `nodes-cleanup-17.txt`.

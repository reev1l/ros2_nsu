# ПР02 — команды и наблюдения

Опыт выполнен 5 октября 2026 года на Ubuntu 26.04.1, ROS 2 Lyrical. В домене 16 уже были `/patrol` и `/turtlesim`, поэтому для изолированного опыта выбран свободный `ROS_DOMAIN_ID=17`. Автоматизация `scripts/run_pr02.py` запускала установленные ROS-команды и сохраняла их вывод в этом каталоге. Qt работал в режиме `offscreen`; ручное наблюдение окна студентом ещё не подтверждено. Список фактически вызванных команд — в `commands.json`, численные результаты — в `measurements.json`.

## Терминал и файлы

| Команда, выполненная из корня репозитория | Назначение | Результат |
| --- | --- | --- |
| `pwd` | Проверить текущий каталог | `/home/reev/Desktop/ROS2` — корень Git и workspace. |
| `mkdir -p src evidence/pr02` | Создать исходный и отчётный каталоги, сохранив существующие | Появились `src/turtle_bringup/` и `evidence/pr02/`. |
| `ls "$(ros2 pkg prefix turtle_bringup)/share/turtle_bringup/launch"` | Проверить установленный ресурс через индекс пакетов | `sim.launch.py`; `ros2 pkg prefix turtle_bringup` вернул `/home/reev/Desktop/ROS2/install/turtle_bringup`. |

`source /opt/ros/lyrical/setup.bash` изменил окружение **текущего** Bash: добавил пути и настройки ROS. `source install/setup.bash` затем добавил установленный пакет workspace. Запуск отдельной программы создал бы дочерний процесс и не мог бы изменить окружение родительского терминала. `export ROS_DOMAIN_ID=17` передал выбранный домен последующим ROS-процессам.

`>` записывает stdout команды в файл, заменяя прежнее содержимое; `2>&1` направляет stderr туда же. `|` передаёт stdout одной команды на stdin другой. В сборке `2>&1 | tee evidence/pr02/build.txt` одновременно вывело текст на экран и сохранило его; `set -o pipefail` сохранил ошибку `colcon` как статус конвейера.

## Сборка и запуск

1. С базовой ROS создан `ament_python` пакет командой `ros2 pkg create --build-type ament_python --license Apache-2.0 turtle_bringup --dependencies launch launch_ros turtlesim`. Его `package.xml` и `setup.py` содержат имя, описание, сопровождающего и зависимости.
2. До появления каталога `launch/` выполнено `colcon build --symlink-install --packages-select turtle_bringup 2>&1 | tee evidence/pr02/build-empty.txt`: `1 package finished`, статус 0. Пакет стал доступен по `ros2 pkg prefix`, но нода от сборки не запустилась.
3. После добавления `launch/sim.launch.py` и записи `data_files` выполнена та же сборка с логом `build.txt`: `1 package finished`, статус 0. Установленный `sim.launch.py` найден через prefix. `python3 -m py_compile src/turtle_bringup/launch/sim.launch.py` завершился успешно.
4. `ros2 launch turtle_bringup sim.launch.py` запустил `/turtlesim`; `ros2 node list --no-daemon --spin-time 2` показал эту ноду. После SIGINT, эквивалента Ctrl+C, список стал пустым. Запуск повторён для опыта. Выводы: `launch-first.txt`, `nodes-first.txt`, `nodes-after-first-stop.txt`, `launch-experiment.txt`, `nodes-experiment.txt`, `nodes-final.txt`.

Файл `sim.launch.py` — описание действия `Node(package='turtlesim', executable='turtlesim_node')` на диске. Его установка и обнаружение через package prefix не означают работающий процесс. Процесс появился только после `ros2 launch`; публикация Twist создала сообщение, которое доставляется лишь при совпадении полного имени топика, типа и совместимых QoS с подпиской.

## Команда, сбой и исправление

`ros2 interface show geometry_msgs/msg/Twist` показал поля в `twist-interface.txt`; `ros2 topic type /turtle1/pose` вернул `turtlesim_msgs/msg/Pose` (`pose-type.txt`). Teleop во время опыта не работал. Отправлялось одно и то же значение Twist: `{linear: {x: 1.0}, angular: {z: 0.5}}`.

| Этап | Команда издателя | Наблюдение |
| --- | --- | --- |
| До сбоя | `ros2 topic pub --once /turtle1/cmd_vel geometry_msgs/msg/Twist '{linear: {x: 1.0}, angular: {z: 0.5}}'` | Поза: `(5.544445, 5.544445, 0)` → `(6.509309, 5.796991, 0.504)`; смещение `0.997368`. Издатель завершился после одного сообщения, черепаха остановилась без новых команд. |
| Сбой | `ros2 topic pub --rate 1 --wait-matching-subscriptions 0 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 1.0}, angular: {z: 0.5}}'` | `ros2 topic info /cmd_vel --verbose`: 1 издатель `_ros2cli_21987`, 0 подписчиков. На `/turtle1/cmd_vel`: 0 издателей, 1 подписчик `/turtlesim`. Поза `(6.509309, 5.796991, 0.504)` не изменилась за наблюдение; смещение `0`. |
| После исправления | Та же команда, только `/cmd_vel` заменено на `/turtle1/cmd_vel` | `ros2 topic info /turtle1/cmd_vel --verbose`: 1 издатель `_ros2cli_22131`, 1 подписчик `/turtlesim`. Поза `(6.509309, 5.796991, 0.504)` → `(6.601517, 9.237254, 2.576)`; смещение `3.441499`. |

В исходных `info-broken.txt`, `info-correct-during-broken.txt`, `info-fixed.txt` также сохранены типы и QoS конечных точек. Публикация в `/cmd_vel` существовала и была видна графу, но у этого **полного имени** не было подписчика. Совпадающий тип Twist сам по себе не пересылает сообщение на другое имя. После исправления издатель и подписчик обнаружили друг друга на `/turtle1/cmd_vel`, доставка возобновилась. Скорость, тип и домен при исправлении не менялись. Издатели и launch остановлены; итоговый список нод в домене 17 пуст.

Начальное направление при `linear.x=1.0` — вперёд по текущему курсу; `angular.z=0.5` — поворот против часовой стрелки. При непрерывной публикации путь изгибается. Однократная публикация не задаёт движение навсегда: turtlesim останавливается без последующих команд.

После остановки исправленного издателя скрипт подождал 1,5 секунды и снова получил позу: `(5.794906, 9.527668, 3.008)`, `linear_velocity=0.0`, `angular_velocity=0.0`. Вывод сохранён в `pose-after-fixed-stop.txt`: черепаха остановилась до завершения launch.

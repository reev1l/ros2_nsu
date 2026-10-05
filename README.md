# ros2_nsu — практические работы по ROS 2

[Условие ПР01](https://ros.lms.ci.nsu.ru/practices/pr01) · [Порядок сдачи](https://ros.lms.ci.nsu.ru/practices/runbook) · [Комплект курса](https://ros.lms.ci.nsu.ru/course/course-kit)

## ПР02: пакет запуска и имя топика

[Условие ПР02](https://ros.lms.ci.nsu.ru/practices/pr02) · [Команды и измерения](evidence/pr02/commands.md) · [Типы сообщений](evidence/pr02/types.md)

Пакет `src/turtle_bringup` устанавливает `sim.launch.py`, который запускает готовую ноду `turtlesim_node`. Собственных ROS-нод в ПР02 нет. Пустой пакет и пакет с launch-файлом собраны отдельно; выводы — `evidence/pr02/build-empty.txt` и `build.txt`. В установленном каталоге launch-файл обнаружен через `ros2 pkg prefix turtle_bringup`.

Повторить автоматический опыт с настоящими ROS-нодами:

```bash
source /opt/ros/lyrical/setup.bash
colcon build --symlink-install --packages-select turtle_bringup
source install/setup.bash
export ROS_DOMAIN_ID=17 # выберите свободный домен
python3 scripts/run_pr02.py
```

Скрипт проверяет запуск и остановку launch, одинарную команду движения, ошибочную публикацию в `/cmd_vel` и исправленную публикацию в `/turtle1/cmd_vel`. Симулятор работает с `QT_QPA_PLATFORM=offscreen`; сохранённые измерения получены от установленного `turtlesim`, но ручную демонстрацию с окном студенту ещё предстоит повторить. В выполненном опыте домен 16 был занят чужими нодами, поэтому использован свободный домен 17.

Для ручной демонстрации запустите `ros2 launch turtle_bringup sim.launch.py` в терминале A, подключив ROS и workspace. В B с тем же доменом отправьте `ros2 topic pub --once /turtle1/cmd_vel geometry_msgs/msg/Twist '{linear: {x: 1.0}, angular: {z: 0.5}}'`. Затем запустите `ros2 topic pub --rate 1 --wait-matching-subscriptions 0 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 1.0}, angular: {z: 0.5}}'` и сравните `ros2 topic info /cmd_vel --verbose` с `ros2 topic info /turtle1/cmd_vel --verbose`. Остановите издателя через Ctrl+C, исправьте только имя топика и повторите. В конце остановите launch через Ctrl+C.

## ПР01: окружение и граф ROS 2

Проверенная среда: Ubuntu 26.04.1, нативный ROS 2 Lyrical, `rmw_fastrtps_cpp`, `turtlesim` 1.10.9. `gz` не найден; версия Gazebo пока не определена. Домен исправного графа — 16, домен разрыва — 17.

Опыт выполнен автоматически настоящими ROS-нодами: Qt-симулятор запущен без окна (`offscreen`), а стрелка отправлена в `turtle_teleop_key` через псевдотерминал. Частота позы — 62,497 Гц; в домене 17 поза не пришла (`exit=124`) и движение прекратилось; после возврата в 16 поза пришла (`exit=0`) и движение восстановилось. Исходные выводы и координаты сохранены в `evidence/pr01/`.

Это автоматический опыт агента, а не ручная демонстрация студентом. Для защиты повторить шаги ниже с окном и клавиатурой. Наличие файлов и успешный CI не заменяют объяснение результата.

Повторить автоматический опыт можно без установки новых пакетов:

```bash
source /opt/ros/lyrical/setup.bash
python3 scripts/run_pr01.py
```

Скрипт проверяет отсутствие посторонних нод в доменах 16/17, запускает реальные `turtlesim_node` и `turtle_teleop_key`, проверяет граф, ввод стрелки, частоту и обе стадии доменного опыта, сохраняет реальные выводы и останавливает созданные процессы. Повторный запуск перезаписывает измерения в текущем evidence: после него нужно заново проверить и оформить отчёт. Полные результаты находятся в [graph.md](evidence/pr01/graph.md).

## 1. Подготовить три Bash-терминала

Остановить прежние ROS-ноды, которые могут мешать опыту. В терминалах **A**, **B** и **C** выполнить:

```bash
cd /home/reev/Desktop/ROS2
source /opt/ros/lyrical/setup.bash
export ROS_DOMAIN_ID=16
```

`source` подключает ROS в текущем терминале. `ROS_DOMAIN_ID` применяется при запуске новой ноды; изменение переменной не переносит уже запущенную ноду в другой домен.

В C подготовить каталог:

```bash
mkdir -p evidence/pr01
```

Отчёт doctor уже получен до запуска графа. При необходимости повторить его:

```bash
ros2 doctor --report > evidence/pr01/doctor.txt 2>&1
```

После повторной записи удалить из отчёта сетевые адреса, MAC-адреса и другие сведения, не относящиеся к работе.

## 2. Запустить исправный граф

В **A** запустить симулятор и оставить работать до завершения всего опыта:

```bash
ros2 run turtlesim turtlesim_node
```

В **B** запустить управление:

```bash
ros2 run turtlesim turtle_teleop_key
```

Нажимать стрелки при фокусе в B. Проверить движение черепахи.

В **C** сохранить наблюдения:

```bash
ros2 node list --no-daemon --spin-time 2 > evidence/pr01/nodes-before.txt
ros2 topic list -t > evidence/pr01/topics-before.txt
ros2 node info /turtlesim > evidence/pr01/turtlesim-info.txt
ros2 topic type /turtle1/pose > evidence/pr01/pose-type.txt
POSE_TYPE=$(ros2 topic type /turtle1/pose)
printf 'POSE_TYPE=%s\n' "$POSE_TYPE"
ros2 topic echo /turtle1/pose --once > evidence/pr01/pose-before.txt
```

Для Lyrical ожидается `turtlesim_msgs/msg/Pose`. Не закрывать C: переменная `POSE_TYPE` нужна при разрыве связи. Если C был закрыт, снова подключить ROS и явно задать подтверждённый тип:

```bash
POSE_TYPE=turtlesim_msgs/msg/Pose
```

Измерить частоту не менее 10 секунд:

```bash
ros2 topic hz /turtle1/pose | tee evidence/pr01/pose-hz.txt
```

Завершить только измерение через Ctrl+C. Записать длительность и фактическую частоту в `graph.md`. Ориентир задания — 60–62,5 Гц, но это не строгий порог; поза публикуется и без движения черепахи.

## 3. Разорвать связь

Симулятор **A** оставить в домене 16. В **B** остановить teleop через Ctrl+C и запустить заново:

```bash
export ROS_DOMAIN_ID=17
ros2 run turtlesim turtle_teleop_key
```

Нажать стрелки в B: черепаха из A не должна двигаться. В **C**:

```bash
export ROS_DOMAIN_ID=17
ros2 node list --no-daemon --spin-time 2 > evidence/pr01/nodes-broken.txt
timeout 5s ros2 topic echo /turtle1/pose "$POSE_TYPE" --once > evidence/pr01/pose-broken.txt 2>&1
result=$?
printf 'exit=%s\n' "$result" | tee evidence/pr01/pose-broken-exit.txt
```

Ожидается `/teleop_turtle` без `/turtlesim`, отсутствие позы и `exit=124`. Код 124 означает истечение таймаута; ошибку импорта или другой код нельзя считать подтверждением разрыва домена. Пустой `pose-broken.txt` при таймауте допустим: отдельный файл сохраняет код возврата.

## 4. Восстановить связь

В **B** остановить teleop, вернуть домен и снова запустить:

```bash
export ROS_DOMAIN_ID=16
ros2 run turtlesim turtle_teleop_key
```

В **C** выполнить тот же тест:

```bash
export ROS_DOMAIN_ID=16
ros2 node list --no-daemon --spin-time 2 > evidence/pr01/nodes-fixed.txt
timeout 5s ros2 topic echo /turtle1/pose "$POSE_TYPE" --once > evidence/pr01/pose-fixed.txt 2>&1
result=$?
printf 'exit=%s\n' "$result" | tee evidence/pr01/pose-fixed-exit.txt
```

Ожидаются обе ноды, сообщение с позой и `exit=0`. Проверить, что стрелки в B снова двигают черепаху. Если discovery ещё не завершилось, повторить наблюдение после обнаружения участников. Затем завершить A и B через Ctrl+C.

## 5. Оформить наблюдения

Вручную составить `evidence/pr01/graph.md` по сохранённым выводам:

- команды, вывод и роли нод;
- полные имена топиков и типы, включая `/turtle1/cmd_vel` и `/turtle1/pose`;
- фактическая частота и длительность измерения;
- сравнение «до / сбой / после», домены A/B/C, коды возврата;
- почему domain mismatch изолировал участников и почему teleop пришлось перезапустить.

В `environment.json` записаны обнаруженные версии, фактические домены и способ запуска автоматического опыта. Поле `experiment_completed` равно `true`. Версия Gazebo пока `null`, потому что CLI `gz` отсутствует; не записывать вымышленную версию. Если Gazebo будет установлен, получить её командой `gz sim --versions`. Gazebo в этом опыте не запускался: симулятором был `turtlesim`.

`report.json` оформляется из шаблона `.course-kit/v1/practices/templates/report.json` после создания коммита реализации. В нём перечислены выполненные проверки графа, частоты, движения, разрыва и восстановления связи. Описание дефекта опирается на сохранённые команды, таймаут и результаты. Часы в поле `time` — нормативная трудоёмкость из условия (одна лабораторная пара и примерно 2 часа самостоятельной работы), а не заявление о посещении занятия.

В `AI_USAGE.md` записаны подготовка и автоматическое выполнение агентом; самостоятельное повторение студентом пока не подтверждено. Для этой ПР указывать `ai_used: true`.

## 6. Проверить и сдать два коммита

На коммите сдачи ПР01 workflow проверял JSON и evidence с зафиксированным course kit. Текущий workflow проверяет ПР02. Живой опыт выполняется локально; собственных нод и `colcon` в ПР01 нет.

1. Завершить файлы реализации: README, CI, `.gitignore`, инструкцию комплекта. Зафиксировать их коммитом **A**, исключив `evidence/` и `AI_USAGE.md`.
2. В `evidence/pr01/report.json` записать полный SHA(A), `course_kit.version = v1-w04` и SHA-256 архива этой ревизии. Заполнить остальные поля шаблона.
3. Выполнить:

   ```bash
   python3 -m json.tool evidence/pr01/environment.json > /dev/null
   python3 .course-kit/v1/tools/check_practice.py PR01 --submission .
   ```

4. После успешной проверки создать **B** только из `evidence/pr01/` и `AI_USAGE.md`. В отчёте оставить SHA(A).
5. Отправить B в GitHub. Сдать ссылку на репозиторий, SHA(B) и ссылку на успешный CI run для B.

Checker проверяет оформление и историю Git. Поведение ROS подтверждается исходными наблюдениями из опыта и повторением на защите.

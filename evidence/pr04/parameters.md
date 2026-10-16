# ПР04

Параметры: `linear_speed=0.5` [0, 1], `turn_rate=0.3` [-1, 1],
`publish_hz=10.0` [1, 30]. Значения проверяются до изменения состояния.

```text
$ ros2 param set /patrol publish_hz 0.0
Setting parameter failed: publish_hz must be finite and in [1.0, 30.0]
$ ros2 param get /patrol publish_hz
Double value is: 10.0
$ ros2 param set /patrol publish_hz 5.0
Set parameter successful
```

Измерения `ros2 topic hz /turtle1/cmd_vel`: исходно 10 Гц,
после отказа 10 Гц, после принятия 5.0 — 5 Гц. Выводы: `hz-*.txt`.
В отдельном коммите `6ef8180` без проверки ноль вызвал
`ZeroDivisionError: division by zero`; traceback — `patrol-defect.txt`.
23 теста пройдены: `tests.txt`. Опыт выполнен агентом без окна.

Выполнены `ros2 service call /clear std_srvs/srv/Empty '{}'`
и `ros2 action list -t`; найден `/turtle1/rotate_absolute`.
Сервис получает один ответ на запрос очистки.
Действие задаёт цель поворота с feedback, результатом и отменой.

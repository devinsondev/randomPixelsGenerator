# Random Pixels Generator

Экспериментальный генератор случайных RGB-изображений на PySide6 с
процедурным анализом структуры, многопроцессной генерацией и воспроизводимым
журналом эксперимента.

## Что делает программа

Каждая параллель работает в отдельном процессе:

```text
frame_seed
  -> random RGB
  -> MvpAnalyzer
  -> если MVP прошёл: RobustAnalyzer
  -> сохранить кандидата при включённом autosave
  -> записать полную строку эксперимента в SQLite
  -> следующий кадр
```

Поддерживается до 16 worker-процессов. У каждого собственные генерация,
анализаторы, статистика, seed и SQLite-база.

## Запуск

### Windows

```powershell
python -m venv .venv --system-site-packages
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

После обычного `git pull` пересоздавать `.venv` не нужно. Повторный
`pip install -r requirements.txt` нужен только если изменились зависимости.

## Порог MVP

Есть два режима.

**Fixed** — используется значение `Порог MVP (fixed/warmup)`.

**Auto percentile** — после прогрева вычисляется порог для верхнего хвоста
распределения MVP. Значение по умолчанию:

```text
Top percentile = 0.01%
Warmup = 10 000 кадров на worker
```

То есть после прогрева примерно верхние 0.01% по MVP score получают шанс пройти
первый фильтр. До окончания прогрева используется fixed-порог.

Percentile считается отдельно для каждого worker постоянным по памяти histogram.
При изменении размеров изображения калибровка percentile начинается заново.

## Структура эксперимента

Каждый Start создаёт новую папку:

```text
experiment_data/
  20260929_120000_ab12cd34/
    manifest.json
    workers/
      worker_01.sqlite3
      worker_02.sqlite3
    candidates/
      mvp/
        worker_01/
          frame_000012345_mvp_2.17.png
          frame_000012345_mvp_2.17.json
      robust/
        worker_01/
          frame_000012345_mvp_2.17_robust_31.44.png
          frame_000012345_mvp_2.17_robust_31.44.json
```

Точный путь текущей сессии показывается прямо в UI.

## Воспроизводимость

Каждый worker получает случайный `worker_seed`. Для каждого frame_id из него
детерминированно выводится отдельный `frame_seed`.

У каждого сохранённого PNG лежит JSON-sidecar с:

- worker_id, worker_seed, frame_seed и frame_id;
- width/height;
- полным набором MVP metrics;
- полным набором Robust metrics, если Robust запускался;
- score и threshold обоих анализаторов;
- SHA-256 исходных RGB-пикселей.

Кадр можно воспроизвести и одновременно проверить хэш:

```powershell
python reproduce_candidate.py path\to\candidate.json
```

Если генерация дала не те же пиксели, утилита завершится с hash mismatch.

## SQLite: вся статистика

Если включён чекбокс `Записывать SQLite`, в
`workers/worker_XX.sqlite3` записывается **каждый** проанализированный кадр,
не только кандидаты. Запись идёт пакетами, чтобы меньше мешать генерации.

Чекбокс можно переключать во время работы. При выключении worker закрывает базу
и полностью убирает SQLite из hot path; генерация, MVP/Robust, percentile и PNG
продолжают работать. При повторном включении запись продолжается в той же базе.
Кадры, созданные пока SQLite был выключен, задним числом в базу не добавляются.

Таблица `frames` содержит:

- frame_id, worker_seed, frame_seed;
- размеры и timestamp;
- fixed/auto режим и Top percentile;
- MVP score, фактический threshold, passed и все metrics в JSON;
- Robust score/threshold/passed и metrics, если он запускался.

У каждого worker своя база, поэтому 16 процессов не дерутся за один SQLite writer.

## CSV

При включённом SQLite это основной журнал эксперимента. После остановки можно выгрузить
каждую worker-базу в CSV без потери FPS во время генерации:

```powershell
python export_csv.py experiment_data\20260929_120000_ab12cd34
```

CSV появятся в `<session>\csv\`.

## Кандидаты

`candidates/mvp/` содержит всё, что прошло первый фильтр.

`candidates/robust/` содержит только кадры, прошедшие и MVP, и Robust.

Robust-кандидат также остаётся в MVP-папке: это намеренно, чтобы уровни отбора
можно было анализировать независимо.

## Важное ограничение

MVP/Robust измеряют **аномальную пространственную структуру относительно шума**,
а не семантический смысл. Следующий смысловой слой — image encoder/VLM — имеет
смысл применять только к редкому хвосту кандидатов, а не ко всем кадрам.


## Clipboard Image Resizer

В `tools/clipboard_resizer/` есть отдельная PySide6-утилита для сравнения
осмысленных изображений с размерами генератора.

Скопируйте любую картинку в буфер и запустите:

```powershell
python tools\clipboard_resizer\main.py
```

Можно задать точные W×H, выбрать Stretch/Fit/Cover и Nearest/Smooth, затем
сохранить результат или скопировать его обратно в буфер.


## Image Batch Sanity Analyzer

Для проверки целой папки реальных изображений:

```powershell
python tools\batch_analyzer\main.py
```

Тулза рекурсивно сканирует папку, приводит каждое изображение к выбранному W×H
и выводит таблицу с маленьким 8×8/16×16 preview и score:

- Real MVP / Robust;
- Shuffled MVP / Robust;
- Random MVP / Robust.

Анализ идёт в отдельном потоке, есть progress и отмена. По завершении выводятся
средние score по всей выборке.

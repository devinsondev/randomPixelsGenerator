# Random Pixels Generator

Минимальный генератор случайных RGB-изображений на PySide6.

## Возможности

- задать ширину и высоту;
- задать интервал между генерациями в миллисекундах;
- запускать/останавливать непрерывную генерацию;
- сгенерировать один кадр;
- включать/выключать отображение изображения;
- сохранить текущую картинку в PNG/JPEG/BMP.

Каждый пиксель получает независимые случайные значения R, G и B от 0 до 255.

## Запуск

### Windows

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Для первого эксперимента удобно начинать с 16×16, 32×32 или 64×64.

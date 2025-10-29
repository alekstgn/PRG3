#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для генерации PDF-чеков для платной автостоянки.
Читает данные из CSV/JSON файлов и генерирует PDF из HTML-шаблонов.
"""

import os
import sys
import json
import csv
import platform
from pathlib import Path
from datetime import datetime

try:
    import pandas as pd
except ImportError:
    pd = None

WEASYPRINT_AVAILABLE = False
try:
    from weasyprint import HTML, CSS  # type: ignore
    from weasyprint.text.fonts import FontConfiguration  # type: ignore
    WEASYPRINT_AVAILABLE = True
except Exception:
    WEASYPRINT_AVAILABLE = False

# Библиотеки для резервной генерации PDF (ReportLab)
REPORTLAB_AVAILABLE = False
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.units import mm
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False


class InvoiceGenerator:
    """Класс для генерации PDF-чеков из данных автостоянки."""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.data_dir = self.base_dir / "data"
        self.templates_dir = self.base_dir / "templates"
        self.output_dir = self.base_dir / "output"
        
        # Создаём директории, если их нет
        self.data_dir.mkdir(exist_ok=True)
        self.templates_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
    
    def get_data_files(self):
        """Получает список доступных CSV и JSON файлов."""
        data_files = []
        
        if self.data_dir.exists():
            for file in self.data_dir.iterdir():
                if file.is_file():
                    if file.suffix.lower() == '.csv':
                        data_files.append(('CSV', file.name))
                    elif file.suffix.lower() == '.json':
                        data_files.append(('JSON', file.name))
        
        return data_files
    
    def get_template_files(self):
        """Получает список доступных HTML-шаблонов."""
        templates = []
        
        if self.templates_dir.exists():
            for file in self.templates_dir.iterdir():
                if file.is_file() and file.suffix.lower() == '.html':
                    templates.append(file.name)
        
        return templates
    
    def read_csv_data(self, filename):
        """Читает данные из CSV файла."""
        filepath = self.data_dir / filename
        
        if pd is not None:
            # Используем pandas, если доступен
            try:
                df = pd.read_csv(filepath, encoding='utf-8')
                # Конвертируем в список словарей
                return df.to_dict('records')
            except Exception as e:
                print(f"Ошибка при чтении CSV через pandas: {e}")
                # Пробуем стандартную библиотеку
                return self._read_csv_standard(filepath)
        else:
            return self._read_csv_standard(filepath)
    
    def _read_csv_standard(self, filepath):
        """Читает CSV файл стандартной библиотекой."""
        data = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data.append(row)
        except Exception as e:
            print(f"Ошибка при чтении CSV: {e}")
            return []
        return data
    
    def read_json_data(self, filename):
        """Читает данные из JSON файла."""
        filepath = self.data_dir / filename
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Если это список словарей, возвращаем как есть
                if isinstance(data, list):
                    return data
                # Если это словарь, возвращаем как список с одним элементом
                elif isinstance(data, dict):
                    return [data]
                else:
                    print("Неверный формат JSON файла")
                    return []
        except Exception as e:
            print(f"Ошибка при чтении JSON: {e}")
            return []
    
    def display_menu(self, title, items, item_type="файл"):
        """Отображает меню выбора с нумерацией."""
        print(f"\n{'='*50}")
        print(f"  {title}")
        print(f"{'='*50}")
        
        if not items:
            print(f"  Доступных {item_type}ов не найдено!")
            return None
        
        for idx, item in enumerate(items, 1):
            if isinstance(item, tuple):
                file_type, filename = item
                print(f"  {idx}. [{file_type}] {filename}")
            else:
                print(f"  {idx}. {item}")
        
        print(f"{'='*50}")
        
        while True:
            try:
                choice = input(f"\nВыберите {item_type} (1-{len(items)}): ").strip()
                choice_num = int(choice)
                if 1 <= choice_num <= len(items):
                    return items[choice_num - 1]
                else:
                    print(f"Пожалуйста, введите число от 1 до {len(items)}")
            except ValueError:
                print("Пожалуйста, введите корректное число")
            except KeyboardInterrupt:
                print("\n\nОперация отменена пользователем.")
                sys.exit(0)
    
    def render_template(self, template_path, data):
        """Подставляет данные в HTML-шаблон."""
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Заменяем все плейсхолдеры вида {{ key }}
            for key, value in data.items():
                placeholder = f"{{{{ {key} }}}}"
                html_content = html_content.replace(placeholder, str(value))
            
            return html_content
        except Exception as e:
            print(f"Ошибка при обработке шаблона: {e}")
            return None
    
    def _register_cyrillic_font(self):
        """Регистрирует TTF-шрифт с поддержкой кириллицы для ReportLab."""
        if not REPORTLAB_AVAILABLE:
            return None
        # Порядок поиска: локальная папка шаблонов → Windows Arial → Roboto/DejaVu
        candidates = [
            self.templates_dir / "fonts" / "DejaVuSans.ttf",
            self.templates_dir / "fonts" / "Roboto-Regular.ttf",
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        ]
        for path in candidates:
            try:
                if path and path.exists():
                    pdfmetrics.registerFont(TTFont("AppCyrillic", str(path)))
                    return "AppCyrillic"
            except Exception:
                continue
        return None

    def _generate_pdf_reportlab(self, data, output_path):
        """Резервная генерация PDF без HTML с помощью ReportLab (кириллица поддерживается)."""
        if not REPORTLAB_AVAILABLE:
            print("ReportLab недоступен. Установите: pip install reportlab")
            return False
        try:
            page_width, page_height = A4
            c = canvas.Canvas(str(output_path), pagesize=A4)

            font_name = self._register_cyrillic_font() or "Helvetica"
            title_font = font_name
            text_font = font_name

            # Заголовок
            c.setFont(title_font, 18)
            c.drawString(20*mm, (page_height - 25*mm), "Чек платной автостоянки")
            c.setFont(text_font, 10)
            c.drawString(20*mm, (page_height - 32*mm), "ООО \"Автостоянка Плюс\" | ИНН: 1234567890")

            # Блок чека
            y = page_height - 50*mm
            c.setFont(text_font, 12)
            def row(label, value):
                nonlocal y
                c.drawString(20*mm, y, f"{label}")
                c.drawString(80*mm, y, f": {value}")
                y -= 8*mm

            row("Номер чека", data.get("invoice_id", "—"))
            row("Марка", data.get("brand", "—"))
            row("Модель", data.get("model", "—"))
            row("Цвет", data.get("color", "—"))
            row("Гос. номер", data.get("registration_number", "—"))
            row("Дата/время въезда", f"{data.get('entry_date','—')} {data.get('entry_time','')}")
            row("Дата/время выезда", f"{data.get('exit_date','—')} {data.get('exit_time','')}")
            row("Тариф за час", f"{data.get('price_per_hour','—')} ₽")

            # Итог
            c.setFont(title_font, 16)
            c.drawString(20*mm, y-4*mm, f"Итого к оплате: {data.get('total_amount','—')} ₽")

            # Подвал
            c.setFont(text_font, 9)
            c.drawString(20*mm, 15*mm, "Спасибо за использование наших услуг! Тел.: +7 (495) 123-45-67")

            c.showPage()
            c.save()
            return True
        except Exception as e:
            print(f"Ошибка при резервной генерации PDF: {e}")
            return False

    def generate_pdf(self, html_content, output_path, data_for_fallback=None):
        """Генерирует PDF: WeasyPrint при наличии, иначе ReportLab (резерв)."""
        if WEASYPRINT_AVAILABLE:
            try:
                font_config = FontConfiguration()
                HTML(string=html_content).write_pdf(
                    output_path,
                    font_config=font_config
                )
                return True
            except Exception as e:
                print(f"Ошибка при генерации PDF WeasyPrint: {e}")
                print("Пробую резервный метод ReportLab...")
        # Резервный путь
        return self._generate_pdf_reportlab(data_for_fallback or {}, output_path)
    
    def open_pdf(self, pdf_path):
        """Автоматически открывает PDF в системной программе."""
        try:
            system = platform.system()
            pdf_path_str = str(pdf_path)
            
            if system == "Windows":
                os.startfile(pdf_path_str)
            elif system == "Darwin":  # macOS
                os.system(f"open '{pdf_path_str}'")
            elif system == "Linux":
                os.system(f"xdg-open '{pdf_path_str}'")
            else:
                print(f"Автоматическое открытие PDF не поддерживается на {system}")
                print(f"Откройте файл вручную: {pdf_path}")
        except Exception as e:
            print(f"Не удалось открыть PDF: {e}")
            print(f"Откройте файл вручную: {pdf_path}")
    
    def run(self):
        """Основная функция запуска скрипта."""
        print("\n" + "="*60)
        print("  ГЕНЕРАТОР ЧЕКОВ ПЛАТНОЙ АВТОСТОЯНКИ")
        print("="*60)
        
        # Получаем списки файлов
        data_files = self.get_data_files()
        template_files = self.get_template_files()
        
        # Выводим доступные файлы
        print("\n📁 Доступные файлы с данными:")
        if data_files:
            for file_type, filename in data_files:
                print(f"   - [{file_type}] {filename}")
        else:
            print("   Не найдено")
        
        print("\n📄 Доступные HTML-шаблоны:")
        if template_files:
            for template in template_files:
                print(f"   - {template}")
        else:
            print("   Не найдено")
        
        # Выбираем файл данных
        selected_data = self.display_menu(
            "Выбор файла с данными",
            data_files,
            "файл данных"
        )
        
        if selected_data is None:
            print("Нет доступных файлов данных.")
            return
        
        file_type, filename = selected_data
        
        # Выбираем шаблон
        selected_template = self.display_menu(
            "Выбор HTML-шаблона",
            template_files,
            "шаблон"
        )
        
        if selected_template is None:
            print("Нет доступных шаблонов.")
            return
        
        # Читаем данные
        print(f"\nЧтение данных из {filename}...")
        if file_type == 'CSV':
            data = self.read_csv_data(filename)
        else:  # JSON
            data = self.read_json_data(filename)
        
        if not data:
            print("Не удалось прочитать данные из файла.")
            return
        
        # Выводим список доступных invoice_id
        print("\n" + "="*50)
        print("  Доступные чеки (invoice_id)")
        print("="*50)
        
        invoices = []
        for idx, record in enumerate(data, 1):
            invoice_id = record.get('invoice_id', f'Не определен ({idx})')
            brand = record.get('brand', 'Не указано')
            model = record.get('model', 'Не указано')
            reg_num = record.get('registration_number', 'Не указано')
            print(f"  {idx}. Invoice ID: {invoice_id} | {brand} {model} | Гос. номер: {reg_num}")
            invoices.append(record)
        
        print("="*50)
        
        # Выбираем invoice
        while True:
            try:
                choice = input(f"\nВыберите чек для генерации (1-{len(invoices)}): ").strip()
                choice_num = int(choice)
                if 1 <= choice_num <= len(invoices):
                    selected_invoice = invoices[choice_num - 1]
                    break
                else:
                    print(f"Пожалуйста, введите число от 1 до {len(invoices)}")
            except ValueError:
                print("Пожалуйста, введите корректное число")
            except KeyboardInterrupt:
                print("\n\nОперация отменена пользователем.")
                return
        
        # Генерируем PDF
        invoice_id = selected_invoice.get('invoice_id', 'unknown')
        template_path = self.templates_dir / selected_template
        
        print(f"\nГенерация PDF для чека #{invoice_id}...")
        
        # Рендерим шаблон
        html_content = self.render_template(template_path, selected_invoice)
        
        if html_content is None:
            print("Ошибка при обработке шаблона.")
            return
        
        # Сохраняем PDF
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"invoice_{invoice_id}_{timestamp}.pdf"
        output_path = self.output_dir / output_filename
        
        if self.generate_pdf(html_content, output_path, data_for_fallback=selected_invoice):
            print(f"✓ PDF успешно создан: {output_path}")
            
            # Автоматически открываем PDF
            print("Открытие PDF...")
            self.open_pdf(output_path)
        else:
            print("Ошибка при создании PDF.")


def main():
    """Точка входа в программу."""
    generator = InvoiceGenerator()
    try:
        generator.run()
    except KeyboardInterrupt:
        print("\n\nПрограмма завершена пользователем.")
        sys.exit(0)
    except Exception as e:
        print(f"\nКритическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()


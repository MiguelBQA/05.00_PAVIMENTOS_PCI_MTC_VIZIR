"""
Interfaz Gráfica AVANZADA para Procesador de Imágenes de Carretera - YOLO
Versión MEJORADA con:
- 🎯 Ajuste de precisión tipo spinner para ángulo
- 📊 Tiles rectangulares (tamaño X e Y independientes)
- 🔍 Zoom en definir polígono
- 📐 Vista previa reorganizada con solapamiento visible
- ✂️ Recorte completo sin restos

Requiere: pip install pillow numpy opencv-python opencv-contrib-python tkinterdnd2
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import tkinter.font as tkfont
from PIL import Image, ImageTk
import numpy as np
import cv2
import os
import math
import threading
import time
import json
import re
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import multiprocessing as mp

# Intentar importar tkinterdnd2 para drag & drop
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DRAG_DROP_AVAILABLE = True
except ImportError:
    DRAG_DROP_AVAILABLE = False

# Detectar soporte GPU
GPU_AVAILABLE = False
try:
    if cv2.cuda.getCudaEnabledDeviceCount() > 0:
        GPU_AVAILABLE = True
        GPU_DEVICE_NAME = cv2.cuda.printCudaDeviceInfo(0)
except:
    GPU_AVAILABLE = False

CPU_CORES = mp.cpu_count()

MACOS_COLORS = {
    'bg': '#f5f5f7',
    'surface': '#ffffff',
    'surface_alt': '#fafafc',
    'border': '#d2d2d7',
    'text': '#1d1d1f',
    'muted': '#6e6e73',
    'accent': '#0a84ff',
    'accent_hover': '#0077ed',
    'accent_soft': '#e8f2ff',
    'success': '#34c759',
    'success_hover': '#28a745',
    'warning': '#ff9f0a',
    'warning_hover': '#f08a00',
    'panel': '#eceef3',
    'canvas': '#1f2329',
    'canvas_text': '#98a2b3',
    'log_bg': '#111827',
    'log_text': '#e5e7eb',
    'selection': '#d9ebff',
}

UI_FONT_FAMILY = 'Arial'
UI_MONO_FONT_FAMILY = 'Consolas'


def _pick_font_family(widget, candidates, fallback):
    try:
        available = set(tkfont.families(widget))
    except tk.TclError:
        return fallback

    for family in candidates:
        if family in available:
            return family
    return fallback


def _create_dialog_header(parent, title, subtitle=""):
    header = ttk.Frame(parent, padding=(18, 16))
    header.pack(fill=tk.X, padx=14, pady=(14, 10))
    ttk.Label(header, text=title, style='Subtitle.TLabel').pack(anchor=tk.W)
    if subtitle:
        ttk.Label(header, text=subtitle, style='Info.TLabel').pack(anchor=tk.W, pady=(4, 0))
    return header


def _style_canvas_widget(canvas, background=None):
    canvas.configure(
        bg=background or MACOS_COLORS['canvas'],
        bd=0,
        relief=tk.FLAT,
        highlightthickness=1,
        highlightbackground=MACOS_COLORS['border'],
        highlightcolor=MACOS_COLORS['accent']
    )


def _style_text_widget(text_widget):
    text_widget.configure(
        bg=MACOS_COLORS['log_bg'],
        fg=MACOS_COLORS['log_text'],
        insertbackground=MACOS_COLORS['accent'],
        selectbackground=MACOS_COLORS['accent'],
        selectforeground='#ffffff',
        relief=tk.FLAT,
        bd=0,
        padx=14,
        pady=14,
        highlightthickness=1,
        highlightbackground=MACOS_COLORS['border'],
        highlightcolor=MACOS_COLORS['accent']
    )


def _style_flat_button(button, variant='accent'):
    styles = {
        'accent': (MACOS_COLORS['accent'], MACOS_COLORS['accent_hover'], '#ffffff'),
        'success': (MACOS_COLORS['success'], MACOS_COLORS['success_hover'], '#ffffff'),
        'warning': (MACOS_COLORS['warning'], MACOS_COLORS['warning_hover'], MACOS_COLORS['text']),
        'neutral': (MACOS_COLORS['surface_alt'], MACOS_COLORS['surface_alt'], MACOS_COLORS['muted']),
    }
    bg, active_bg, fg = styles.get(variant, styles['accent'])
    button.configure(
        bg=bg,
        fg=fg,
        activebackground=active_bg,
        activeforeground=fg,
        relief=tk.FLAT,
        bd=0,
        padx=16,
        pady=9,
        cursor='hand2',
        highlightthickness=0,
        disabledforeground=MACOS_COLORS['muted'],
        font=(UI_FONT_FAMILY, 10, 'bold')
    )


class GPUAccelerator:
    """Clase para manejar aceleración GPU"""
    
    @staticmethod
    def is_available():
        return GPU_AVAILABLE
    
    @staticmethod
    def rotate_gpu(img_array: np.ndarray, angulo: float, center: Tuple[int, int]) -> np.ndarray:
        if not GPU_AVAILABLE:
            return None
        
        try:
            gpu_img = cv2.cuda_GpuMat()
            gpu_img.upload(img_array)
            
            h, w = img_array.shape[:2]
            M = cv2.getRotationMatrix2D(center, angulo, 1.0)
            
            cos = np.abs(M[0, 0])
            sin = np.abs(M[0, 1])
            new_w = int((h * sin) + (w * cos))
            new_h = int((h * cos) + (w * sin))
            
            M[0, 2] += (new_w / 2) - center[0]
            M[1, 2] += (new_h / 2) - center[1]
            
            gpu_rotada = cv2.cuda.warpAffine(gpu_img, M, (new_w, new_h), 
                                            flags=cv2.INTER_LINEAR,
                                            borderMode=cv2.BORDER_CONSTANT,
                                            borderValue=(255, 255, 255))
            
            result = gpu_rotada.download()
            return result
            
        except Exception as e:
            print(f"Error GPU: {e}")
            return None


class PolygonSelectorWindow:
    """Ventana para seleccionar polígono de área de interés CON ZOOM"""
    
    def __init__(self, parent, image_path: str, image_name: str, existing_polygon=None):
        self.window = tk.Toplevel(parent)
        self.window.title(f"Recortar Área - {image_name}")
        self.window.geometry("1200x800")
        self.window.configure(bg=MACOS_COLORS['bg'])
        
        self.image_path = image_path
        self.image_name = image_name
        self.polygon_points = existing_polygon if existing_polygon else []
        self.temp_points = []
        self.result = None
        self.drawing_complete = False
        
        # Variables de zoom
        self.zoom_level = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.drag_start_x = 0
        self.drag_start_y = 0
        
        self.img_original = cv2.imread(image_path)
        if self.img_original is None:
            messagebox.showerror("Error", f"No se pudo cargar: {image_path}")
            self.window.destroy()
            return
        
        self.img_original = cv2.cvtColor(self.img_original, cv2.COLOR_BGR2RGB)
        self.img_work = self.img_original.copy()
        
        self._setup_ui()
        self._update_canvas()
        
        self.window.transient(parent)
        self.window.grab_set()
    
    def _setup_ui(self):
        _create_dialog_header(
            self.window,
            f"Recortar área - {self.image_name}",
            "Define el polígono de interés con zoom y desplazamiento."
        )

        top_frame = ttk.Frame(self.window, padding=10)
        top_frame.pack(fill=tk.X, padx=14)
        
        # Instrucciones
        inst_frame = ttk.Frame(top_frame)
        inst_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(inst_frame, text="🔷 Dibuja un polígono alrededor de la carretera:", 
                 font=(UI_FONT_FAMILY, 11, 'bold')).pack(anchor=tk.W)
        ttk.Label(inst_frame, 
                 text="• Click izquierdo: agregar punto | Click derecho: cerrar polígono | Ctrl+Z: deshacer",
                 font=(UI_FONT_FAMILY, 9)).pack(anchor=tk.W, padx=20)
        
        # Controles de zoom
        zoom_frame = ttk.LabelFrame(top_frame, text="🔍 Zoom", padding=5)
        zoom_frame.pack(side=tk.RIGHT, padx=10)
        
        ttk.Button(zoom_frame, text="🔍+", width=5,
                  command=lambda: self._zoom(1.2)).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_frame, text="🔍-", width=5,
                  command=lambda: self._zoom(0.8)).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_frame, text="1:1", width=5,
                  command=self._reset_zoom).pack(side=tk.LEFT, padx=2)
        
        self.zoom_label = ttk.Label(zoom_frame, text="100%", font=(UI_FONT_FAMILY, 10, 'bold'))
        self.zoom_label.pack(side=tk.LEFT, padx=5)
        
        # Canvas con scrollbars
        canvas_frame = ttk.Frame(self.window)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=5)
        
        h_scroll = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        
        v_scroll = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.canvas = tk.Canvas(canvas_frame, bg=MACOS_COLORS['canvas'], cursor='crosshair',
                               xscrollcommand=h_scroll.set,
                               yscrollcommand=v_scroll.set)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        _style_canvas_widget(self.canvas, MACOS_COLORS['canvas'])
        
        h_scroll.config(command=self.canvas.xview)
        v_scroll.config(command=self.canvas.yview)
        
        # Bindings
        self.canvas.bind('<Button-1>', self._on_left_click)
        self.canvas.bind('<Button-3>', self._on_right_click)
        self.canvas.bind('<Double-Button-1>', self._on_double_click)
        self.canvas.bind('<MouseWheel>', self._on_mousewheel)
        self.canvas.bind('<ButtonPress-2>', self._on_middle_press)  # Rueda presionada
        self.canvas.bind('<B2-Motion>', self._on_middle_drag)
        
        self.window.bind('<Control-z>', self._undo_point)
        self.window.bind('<Escape>', lambda e: self._on_cancel())
        self.window.bind('<Return>', lambda e: self._on_confirm())
        
        # Barra inferior
        bottom_frame = ttk.Frame(self.window, padding=10)
        bottom_frame.pack(fill=tk.X, padx=14, pady=(0, 10))
        
        self.status_label = ttk.Label(bottom_frame,
                                      text="Click para agregar puntos al polígono...",
                                      font=(UI_FONT_FAMILY, 10))
        self.status_label.pack(side=tk.LEFT)
        
        btn_frame = ttk.Frame(bottom_frame)
        btn_frame.pack(side=tk.RIGHT)
        
        ttk.Button(btn_frame, text="❌ Cancelar", 
                  command=self._on_cancel).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(btn_frame, text="⟲ Reiniciar", 
                  command=self._on_reset).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(btn_frame, text="⬜ Área Completa", 
                  command=self._use_full_image).pack(side=tk.LEFT, padx=2)
        
        self.btn_confirm = ttk.Button(btn_frame, text="✓ Confirmar Polígono", 
                                     command=self._on_confirm, state=tk.DISABLED)
        self.btn_confirm.pack(side=tk.LEFT, padx=2)
    
    def _zoom(self, factor):
        """Aplica zoom"""
        new_zoom = self.zoom_level * factor
        new_zoom = max(0.1, min(10.0, new_zoom))
        self.zoom_level = new_zoom
        self.zoom_label.config(text=f"{int(new_zoom * 100)}%")
        self._update_canvas()
    
    def _reset_zoom(self):
        """Reset zoom"""
        self.zoom_level = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.zoom_label.config(text="100%")
        self._update_canvas()
    
    def _on_mousewheel(self, event):
        """Zoom con rueda"""
        if event.delta > 0:
            self._zoom(1.1)
        else:
            self._zoom(0.9)
    
    def _on_middle_press(self, event):
        """Inicia arrastre"""
        self.drag_start_x = event.x
        self.drag_start_y = event.y
    
    def _on_middle_drag(self, event):
        """Arrastra la vista"""
        if self.zoom_level > 1.0:
            dx = event.x - self.drag_start_x
            dy = event.y - self.drag_start_y
            
            self.canvas.xview_scroll(-int(dx), "units")
            self.canvas.yview_scroll(-int(dy), "units")
            
            self.drag_start_x = event.x
            self.drag_start_y = event.y
    
    def _update_canvas(self):
        """Actualiza canvas con zoom"""
        # Aplicar zoom
        h, w = self.img_work.shape[:2]
        new_w = int(w * self.zoom_level)
        new_h = int(h * self.zoom_level)
        
        if new_w > 0 and new_h > 0:
            zoomed = cv2.resize(self.img_work, (new_w, new_h), 
                              interpolation=cv2.INTER_LINEAR if self.zoom_level > 1 else cv2.INTER_AREA)
        else:
            zoomed = self.img_work
        
        pil_img = Image.fromarray(zoomed)
        self.photo = ImageTk.PhotoImage(pil_img)
        
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
        self.canvas.config(scrollregion=(0, 0, new_w, new_h))
    
    def _get_original_coords(self, canvas_x, canvas_y):
        """Convierte coordenadas del canvas a coordenadas de imagen original"""
        x_orig = int(canvas_x / self.zoom_level)
        y_orig = int(canvas_y / self.zoom_level)
        return x_orig, y_orig
    
    def _get_canvas_coords(self, orig_x, orig_y):
        """Convierte coordenadas originales a canvas"""
        x_canvas = int(orig_x * self.zoom_level)
        y_canvas = int(orig_y * self.zoom_level)
        return x_canvas, y_canvas
    
    def _on_left_click(self, event):
        if self.drawing_complete:
            return
        
        x_orig, y_orig = self._get_original_coords(event.x, event.y)
        
        self.temp_points.append((x_orig, y_orig))
        
        # Redibujar
        self._redraw_work_image()
        
        self.status_label.config(text=f"Puntos: {len(self.temp_points)} | Click derecho o doble-click para cerrar")
        
        if len(self.temp_points) >= 3:
            self.btn_confirm.config(state=tk.NORMAL)
        
        self._update_canvas()
    
    def _redraw_work_image(self):
        """Redibuja la imagen de trabajo con los puntos actuales"""
        self.img_work = self.img_original.copy()
        
        if len(self.temp_points) == 0:
            return
        
        # Dibujar puntos
        for i, (x, y) in enumerate(self.temp_points):
            cv2.circle(self.img_work, (x, y), 5, (0, 255, 0), -1)
            cv2.putText(self.img_work, str(i+1), (x+10, y-10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # Dibujar líneas
        if len(self.temp_points) > 1:
            for i in range(len(self.temp_points) - 1):
                cv2.line(self.img_work, self.temp_points[i], self.temp_points[i+1], 
                        (0, 255, 255), 2)
    
    def _on_right_click(self, event):
        self._close_polygon()
    
    def _on_double_click(self, event):
        self._close_polygon()
    
    def _close_polygon(self):
        if len(self.temp_points) < 3:
            messagebox.showwarning("Advertencia", "Necesitas al menos 3 puntos para formar un polígono")
            return
        
        self.drawing_complete = True
        
        self.img_work = self.img_original.copy()
        
        # Rellenar polígono
        overlay = self.img_work.copy()
        pts = np.array(self.temp_points, np.int32)
        cv2.fillPoly(overlay, [pts], (0, 255, 0))
        cv2.addWeighted(overlay, 0.3, self.img_work, 0.7, 0, self.img_work)
        
        # Dibujar borde
        cv2.polylines(self.img_work, [pts], True, (0, 255, 0), 3)
        
        # Dibujar puntos
        for i, pt in enumerate(self.temp_points):
            cv2.circle(self.img_work, pt, 5, (255, 0, 0), -1)
            cv2.putText(self.img_work, str(i+1), (pt[0]+10, pt[1]-10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
        
        self.status_label.config(text=f"✓ Polígono cerrado con {len(self.temp_points)} puntos")
        self.btn_confirm.config(state=tk.NORMAL)
        
        self._update_canvas()
    
    def _undo_point(self, event=None):
        if self.temp_points and not self.drawing_complete:
            self.temp_points.pop()
            
            self._redraw_work_image()
            
            self.status_label.config(text=f"Puntos: {len(self.temp_points)}")
            
            if len(self.temp_points) < 3:
                self.btn_confirm.config(state=tk.DISABLED)
            
            self._update_canvas()
    
    def _on_reset(self):
        self.temp_points = []
        self.drawing_complete = False
        self.img_work = self.img_original.copy()
        self._update_canvas()
        self.status_label.config(text="Click para agregar puntos al polígono...")
        self.btn_confirm.config(state=tk.DISABLED)
    
    def _use_full_image(self):
        h, w = self.img_original.shape[:2]
        self.temp_points = [(0, 0), (w, 0), (w, h), (0, h)]
        self.drawing_complete = True
        
        self.img_work = self.img_original.copy()
        cv2.rectangle(self.img_work, (0, 0), (w, h), (0, 255, 0), 3)
        
        self.status_label.config(text="✓ Usando área completa de la imagen")
        self.btn_confirm.config(state=tk.NORMAL)
        
        self._update_canvas()
    
    def _on_confirm(self):
        if len(self.temp_points) >= 3:
            self.result = self.temp_points
            self.window.destroy()
    
    def _on_cancel(self):
        self.result = None
        self.window.destroy()
    
    def get_result(self):
        self.window.wait_window()
        return self.result


class ImageSelectorWindow:
    """Ventana para seleccionar puntos del eje"""
    
    def __init__(self, parent, image_path: str, image_name: str):
        self.window = tk.Toplevel(parent)
        self.window.title(f"Seleccionar Eje - {image_name}")
        self.window.geometry("1000x700")
        self.window.configure(bg=MACOS_COLORS['bg'])
        
        self.image_path = image_path
        self.image_name = image_name
        self.puntos = []
        self.result = None
        
        self.img_original = cv2.imread(image_path)
        if self.img_original is None:
            messagebox.showerror("Error", f"No se pudo cargar: {image_path}")
            self.window.destroy()
            return
        
        self.scale = self._calculate_scale()
        self.img_display = cv2.resize(self.img_original, 
                                     (int(self.img_original.shape[1] * self.scale),
                                      int(self.img_original.shape[0] * self.scale)))
        self.img_display = cv2.cvtColor(self.img_display, cv2.COLOR_BGR2RGB)
        self.img_work = self.img_display.copy()
        
        self._setup_ui()
        self._update_canvas()
        
        self.window.transient(parent)
        self.window.grab_set()
    
    def _calculate_scale(self):
        max_display = 900
        h, w = self.img_original.shape[:2]
        if max(h, w) > max_display:
            return max_display / max(h, w)
        return 1.0
    
    def _setup_ui(self):
        _create_dialog_header(
            self.window,
            f"Seleccionar eje - {self.image_name}",
            "Marca el inicio y el fin del tramo para definir el eje."
        )

        top_frame = ttk.Frame(self.window, padding=10)
        top_frame.pack(fill=tk.X, padx=14)
        
        ttk.Label(top_frame, text="📍 Instrucciones:", 
                 font=(UI_FONT_FAMILY, 11, 'bold')).pack(anchor=tk.W)
        ttk.Label(top_frame, 
                 text="1. Click en DOS puntos que marquen el EJE de la carretera",
                 font=(UI_FONT_FAMILY, 10)).pack(anchor=tk.W, padx=20)
        ttk.Label(top_frame, 
                 text="   • Punto 1: INICIO del tramo (parte superior)",
                 font=(UI_FONT_FAMILY, 9)).pack(anchor=tk.W, padx=40)
        ttk.Label(top_frame, 
                 text="   • Punto 2: FIN del tramo (parte inferior)",
                 font=(UI_FONT_FAMILY, 9)).pack(anchor=tk.W, padx=40)
        
        canvas_frame = ttk.Frame(self.window)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=5)
        
        self.canvas = tk.Canvas(canvas_frame, bg=MACOS_COLORS['canvas'], cursor='crosshair')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        _style_canvas_widget(self.canvas, MACOS_COLORS['canvas'])
        self.canvas.bind('<Button-1>', self._on_click)
        
        bottom_frame = ttk.Frame(self.window, padding=10)
        bottom_frame.pack(fill=tk.X, padx=14, pady=(0, 10))
        
        self.status_label = ttk.Label(bottom_frame,
                                      text="Esperando primer punto...",
                                      font=(UI_FONT_FAMILY, 10))
        self.status_label.pack(side=tk.LEFT)
        
        ttk.Button(bottom_frame, text="❌ Cancelar", 
                  command=self._on_cancel).pack(side=tk.RIGHT, padx=5)
        
        self.btn_confirm = ttk.Button(bottom_frame, text="✓ Confirmar", 
                                     command=self._on_confirm, state=tk.DISABLED)
        self.btn_confirm.pack(side=tk.RIGHT, padx=5)
        
        ttk.Button(bottom_frame, text="🔄 Reiniciar", 
                  command=self._on_reset).pack(side=tk.RIGHT, padx=5)
    
    def _update_canvas(self):
        pil_img = Image.fromarray(self.img_work)
        self.photo = ImageTk.PhotoImage(pil_img)
        
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
        self.canvas.config(scrollregion=self.canvas.bbox("all"))
    
    def _on_click(self, event):
        if len(self.puntos) >= 2:
            return
        
        x_display, y_display = event.x, event.y
        x_orig = int(x_display / self.scale)
        y_orig = int(y_display / self.scale)
        
        self.puntos.append((x_orig, y_orig))
        
        cv2.circle(self.img_work, (x_display, y_display), 8, (0, 255, 0), -1)
        cv2.putText(self.img_work, f"P{len(self.puntos)}", 
                   (x_display + 10, y_display - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        if len(self.puntos) == 2:
            p1_display = (int(self.puntos[0][0] * self.scale), 
                         int(self.puntos[0][1] * self.scale))
            p2_display = (int(self.puntos[1][0] * self.scale), 
                         int(self.puntos[1][1] * self.scale))
            cv2.line(self.img_work, p1_display, p2_display, (255, 0, 0), 3)
            
            self.status_label.config(text=f"✓ Puntos: P1{self.puntos[0]} → P2{self.puntos[1]}")
            self.btn_confirm.config(state=tk.NORMAL)
        else:
            self.status_label.config(text=f"Punto {len(self.puntos)} marcado. Selecciona punto {len(self.puntos)+1}...")
        
        self._update_canvas()
    
    def _on_reset(self):
        self.puntos = []
        self.img_work = self.img_display.copy()
        self._update_canvas()
        self.status_label.config(text="Esperando primer punto...")
        self.btn_confirm.config(state=tk.DISABLED)
    
    def _on_confirm(self):
        if len(self.puntos) == 2:
            self.result = self.puntos
            self.window.destroy()
    
    def _on_cancel(self):
        self.result = None
        self.window.destroy()
    
    def get_result(self):
        self.window.wait_window()
        return self.result


class ImageConfigWindow:
    """Ventana para configurar parámetros individuales de una imagen CON TILES X/Y"""
    
    def __init__(self, parent, image_name: str, config: dict):
        self.window = tk.Toplevel(parent)
        self.window.title(f"Configuración - {image_name}")
        self.window.geometry("500x600")
        self.window.configure(bg=MACOS_COLORS['bg'])
        
        self.image_name = image_name
        self.result = None
        
        # Variables
        self.tile_size_x = tk.IntVar(value=config.get('tile_size_x', 820))
        self.tile_size_y = tk.IntVar(value=config.get('tile_size_y', 820))
        self.overlap = tk.IntVar(value=config.get('overlap', 5))
        
        self._setup_ui()
        
        self.window.transient(parent)
        self.window.grab_set()
    
    def _setup_ui(self):
        _create_dialog_header(
            self.window,
            "Configuración individual",
            self.image_name
        )
        
        # Main frame con scroll
        main_canvas = tk.Canvas(self.window, highlightthickness=0, bg=MACOS_COLORS['surface'])
        main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        _style_canvas_widget(main_canvas, MACOS_COLORS['surface'])
        
        scrollbar = ttk.Scrollbar(self.window, orient=tk.VERTICAL, command=main_canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        main_canvas.configure(yscrollcommand=scrollbar.set)
        
        main = ttk.Frame(main_canvas, padding=15)
        main_canvas.create_window((0, 0), window=main, anchor=tk.NW)
        
        # Tiles
        tiles_frame = ttk.LabelFrame(main, text="Configuración de Tiles", padding=10)
        tiles_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(tiles_frame, text="Ancho X (px):").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Spinbox(tiles_frame, from_=256, to=2048, increment=64,
                   textvariable=self.tile_size_x, width=15).grid(row=0, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(tiles_frame, text="Alto Y (px):").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Spinbox(tiles_frame, from_=256, to=2048, increment=64,
                   textvariable=self.tile_size_y, width=15).grid(row=1, column=1, sticky=tk.W, padx=5)
        
        ttk.Button(tiles_frame, text="🔄 Igualar", 
                  command=self._equalize_tiles).grid(row=0, column=2, rowspan=2, padx=5)
        
        ttk.Label(tiles_frame, text="Solapamiento (px):").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Spinbox(tiles_frame, from_=0, to=200, increment=5,
                   textvariable=self.overlap, width=15).grid(row=2, column=1, sticky=tk.W, padx=5)
        
        # Actualizar scroll region
        main.update_idletasks()
        main_canvas.config(scrollregion=main_canvas.bbox("all"))
        
        # Botones
        btn_frame = ttk.Frame(self.window, padding=15)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=14, pady=(0, 10))
        
        ttk.Button(btn_frame, text="❌ Cancelar",
                  command=self._on_cancel).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text="💾 Guardar",
                  command=self._on_save).pack(side=tk.RIGHT, padx=5)
    
    def _equalize_tiles(self):
        """Iguala el tamaño Y al X"""
        self.tile_size_y.set(self.tile_size_x.get())
    
    def _on_save(self):
        self.result = {
            'tile_size_x': self.tile_size_x.get(),
            'tile_size_y': self.tile_size_y.get(),
            'overlap': self.overlap.get()
        }
        self.window.destroy()
    
    def _on_cancel(self):
        self.result = None
        self.window.destroy()
    
    def get_result(self):
        self.window.wait_window()
        return self.result


class RoadImageProcessor:
    """Clase que contiene la lógica de procesamiento CON RECORTE COMPLETO"""
    
    @staticmethod
    def calcular_angulo_rotacion(p1: Tuple[int, int], p2: Tuple[int, int]) -> float:
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        angulo_rad = math.atan2(dx, dy)
        angulo_deg = math.degrees(angulo_rad)
        return angulo_deg
    
    @staticmethod
    def rotar_imagen(img_array: np.ndarray, angulo: float, 
                    center: Optional[Tuple[int, int]] = None,
                    use_gpu: bool = False) -> np.ndarray:
        h, w = img_array.shape[:2]
        
        if center is None:
            center = (w // 2, h // 2)
        
        if use_gpu and GPU_AVAILABLE:
            result = GPUAccelerator.rotate_gpu(img_array, angulo, center)
            if result is not None:
                return result
        
        M = cv2.getRotationMatrix2D(center, angulo, 1.0)
        
        cos = np.abs(M[0, 0])
        sin = np.abs(M[0, 1])
        new_w = int((h * sin) + (w * cos))
        new_h = int((h * cos) + (w * sin))
        
        M[0, 2] += (new_w / 2) - center[0]
        M[1, 2] += (new_h / 2) - center[1]
        
        rotada = cv2.warpAffine(img_array, M, (new_w, new_h), 
                                borderMode=cv2.BORDER_CONSTANT,
                                borderValue=(255, 255, 255))
        
        return rotada
    
    @staticmethod
    def eliminar_bordes_blancos(img_array: np.ndarray, umbral: int = 250) -> Tuple[np.ndarray, dict]:
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        coords = cv2.findNonZero((gray < umbral).astype(np.uint8))
        
        if coords is not None:
            x, y, w, h = cv2.boundingRect(coords)
            img_recortada = img_array[y:y+h, x:x+w]
            
            original_pixels = img_array.shape[0] * img_array.shape[1]
            final_pixels = img_recortada.shape[0] * img_recortada.shape[1]
            reduccion = ((original_pixels - final_pixels) / original_pixels) * 100
            
            estadisticas = {
                'reduccion_porcentaje': reduccion,
                'dim_original': (img_array.shape[1], img_array.shape[0]),
                'dim_final': (img_recortada.shape[1], img_recortada.shape[0]),
                'pixeles_eliminados': original_pixels - final_pixels
            }
            
            return img_recortada, estadisticas
        else:
            estadisticas = {
                'reduccion_porcentaje': 0.0,
                'dim_original': (img_array.shape[1], img_array.shape[0]),
                'dim_final': (img_array.shape[1], img_array.shape[0]),
                'pixeles_eliminados': 0
            }
            return img_array, estadisticas
    
    @staticmethod
    def procesar_imagen(input_path: str, output_dir: str, puntos: List[Tuple[int, int]],
                       tile_size_x: int = 640, tile_size_y: int = 640, overlap: int = 0,
                       polygon: Optional[List[Tuple[int, int]]] = None,
                       angulo_manual: Optional[float] = None,
                       use_gpu: bool = False,
                       skip_last_tile: bool = False,
                       progress_callback=None,
                       export_format: str = "PNG",
                       use_subfolder: bool = True) -> int:
        """Procesa una imagen CON RECORTE COMPLETO (sin dejar restos)"""
        nombre_archivo = os.path.basename(input_path)
        nombre_base = os.path.splitext(nombre_archivo)[0]
        if use_subfolder:
            output_subdir = os.path.join(output_dir, nombre_base)
        else:
            output_subdir = output_dir
        os.makedirs(output_subdir, exist_ok=True)
        
        if progress_callback:
            progress_callback(f"Procesando: {nombre_archivo}")
        
        p1, p2 = puntos
        
        start_time = time.time()
        img = Image.open(input_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img_array = np.array(img)
        original_shape = img_array.shape
        
        offset_x, offset_y = 0, 0
        
        if polygon and len(polygon) >= 3:
            if progress_callback:
                progress_callback(f"  Aplicando recorte por polígono...")
            
            mask = np.zeros(img_array.shape[:2], dtype=np.uint8)
            pts = np.array(polygon, np.int32)
            cv2.fillPoly(mask, [pts], 255)
            
            result = np.ones_like(img_array) * 255
            result[mask == 255] = img_array[mask == 255]
            
            x_coords = [p[0] for p in polygon]
            y_coords = [p[1] for p in polygon]
            x_min, x_max = max(0, min(x_coords)), min(img_array.shape[1], max(x_coords))
            y_min, y_max = max(0, min(y_coords)), min(img_array.shape[0], max(y_coords))
            
            img_array = result[y_min:y_max, x_min:x_max]
            offset_x, offset_y = x_min, y_min
            p1 = (p1[0] - offset_x, p1[1] - offset_y)
            p2 = (p2[0] - offset_x, p2[1] - offset_y)
            
            if progress_callback:
                cropped_area = (x_max - x_min) * (y_max - y_min)
                original_area = original_shape[0] * original_shape[1]
                percentage = (cropped_area / original_area) * 100
                progress_callback(f"  Recorte polígono: {img_array.shape[1]}x{img_array.shape[0]} ({percentage:.1f}%)")
        
        if angulo_manual is not None:
            angulo = angulo_manual
            if progress_callback:
                progress_callback(f"  Rotación MANUAL: {angulo:.2f}°")
        else:
            angulo = RoadImageProcessor.calcular_angulo_rotacion(p1, p2)
            if progress_callback:
                progress_callback(f"  Rotación AUTOMÁTICA: {angulo:.2f}°")
        
        if progress_callback:
            gpu_status = " (GPU)" if use_gpu and GPU_AVAILABLE else " (CPU)"
            progress_callback(f"  Rotando imagen{gpu_status}...")
        
        img_rotada = RoadImageProcessor.rotar_imagen(img_array, angulo, use_gpu=use_gpu)
        
        if progress_callback:
            progress_callback(f"  Eliminando bordes blancos...")
        
        img_rotada_limpia, stats_bordes = RoadImageProcessor.eliminar_bordes_blancos(img_rotada)
        
        if progress_callback and stats_bordes['reduccion_porcentaje'] > 0:
            progress_callback(f"  ✓ Bordes blancos: -{stats_bordes['reduccion_porcentaje']:.1f}%")
        
        img_rotada = img_rotada_limpia

        img_rotada_pil = Image.fromarray(img_rotada)
        angulo_str = f"{angulo:.2f}".replace('.', '_').replace('-', 'neg')
        rotada_path = os.path.join(output_subdir, f"{nombre_base}_rot_{angulo_str}.png")
        img_rotada_pil.save(rotada_path, "PNG")
        
        if polygon and len(polygon) >= 3:
            cropped_preview = Image.fromarray(img_array)
            cropped_path = os.path.join(output_subdir, "_preview_recortada.png")
            cropped_preview.save(cropped_path, "PNG")
        
        if progress_callback:
            progress_callback(f"  Dividiendo en tiles {tile_size_x}x{tile_size_y} (overlap={overlap})...")
        
        # FORMATO DE EXPORTACIÓN: {nombre_archivo}_{numero}.png
        # Ejemplo: "imagen_carretera_000001.png"
        height_r, width_r = img_rotada.shape[:2]
        
        # ALGORITMO MEJORADO: Recorte completo sin dejar restos
        # Calcular cuántos tiles caben con el solapamiento
        step_x = tile_size_x - overlap
        step_y = tile_size_y - overlap
        
        # Calcular número de tiles necesarios para cubrir toda la imagen
        num_tiles_x = math.ceil((width_r - overlap) / step_x)
        num_tiles_y = math.ceil((height_r - overlap) / step_y)
        
        tile_count = 0
        
        total_tiles_posibles = num_tiles_x * num_tiles_y
        tiles_procesados = 0
        
        for idx_y in range(num_tiles_y):
            for idx_x in range(num_tiles_x):
                # Calcular posición del tile
                x = idx_x * step_x
                y = idx_y * step_y
                
                # Ajustar si nos pasamos del borde
                x_end = min(x + tile_size_x, width_r)
                y_end = min(y + tile_size_y, height_r)
                
                # Si es el último tile en esa dirección, ajustamos el inicio
                # para que el tile tenga el tamaño completo
                is_adjusted_x = False
                is_adjusted_y = False

                if x_end == width_r and (x_end - x) < tile_size_x:
                    x = max(0, width_r - tile_size_x)
                    x_end = width_r
                    if idx_x > 0:
                        is_adjusted_x = True

                if y_end == height_r and (y_end - y) < tile_size_y:
                    y = max(0, height_r - tile_size_y)
                    y_end = height_r
                    if idx_y > 0:
                        is_adjusted_y = True

                if skip_last_tile and (is_adjusted_x or is_adjusted_y):
                    tiles_procesados += 1
                    continue

                # Extraer tile
                tile = img_rotada[y:y_end, x:x_end]
                
                # Verificar que tenga el tamaño correcto
                if tile.shape[0] != tile_size_y or tile.shape[1] != tile_size_x:
                    # Si no tiene el tamaño exacto, hacer padding con blanco
                    padded_tile = np.ones((tile_size_y, tile_size_x, 3), dtype=np.uint8) * 255
                    padded_tile[:tile.shape[0], :tile.shape[1]] = tile
                    tile = padded_tile
                
                # Verificar que no sea mayormente blanco
                white_pixels = np.sum(np.all(tile > 250, axis=2))
                total_pixels = tile_size_x * tile_size_y
                
                if white_pixels / total_pixels < 0.90:
                    # Formato: nombrearchivo_000000.ext
                    if export_format == "TIFF":
                        ext = ".tif"
                    else:
                        ext = ".png"
                    output_filename = f"{nombre_base}_{tile_count:06d}{ext}"
                    output_path = os.path.join(output_subdir, output_filename)

                    tile_pil = Image.fromarray(tile)
                    if export_format == "TIFF":
                        tile_pil.save(output_path, "TIFF", compression="tiff_lzw")
                    else:
                        tile_pil.save(output_path, "PNG", compress_level=6)

                    tile_count += 1
                
                tiles_procesados += 1
                if progress_callback and total_tiles_posibles > 0 and tiles_procesados % 10 == 0:
                    progreso = (tiles_procesados / total_tiles_posibles) * 100
                    progress_callback(f"  Tiles generados: {tile_count}", progreso)
        
        # Guardar metadata del grid para reconstruccion posterior
        try:
            metadata = {
                'grid_columns': num_tiles_x,
                'grid_rows': num_tiles_y,
                'tile_size_x': tile_size_x,
                'tile_size_y': tile_size_y,
                'overlap': overlap,
                'image_width': width_r,
                'image_height': height_r,
                'total_tiles': tile_count,
                'source_file': nombre_archivo
            }
            metadata_path = os.path.join(output_subdir, '_tile_info.json')
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
        except Exception:
            pass  # No fallar si no se puede guardar metadata

        total_time = time.time() - start_time
        
        if progress_callback:
            progress_callback(f"  ✓ Completado: {tile_count} tiles | "
                            f"Total: {total_time:.1f}s")
        
        return tile_count

    @staticmethod
    def _safe_filename(value: str) -> str:
        """Convierte un nombre de grupo en un nombre de archivo seguro."""
        clean = re.sub(r'[<>:"/\\|?*]+', '_', value)
        clean = re.sub(r'\s+', '_', clean).strip('._ ')
        return clean or "join"

    @staticmethod
    def _supported_image_extensions() -> set:
        return {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}

    @staticmethod
    def _image_record(file_path: str) -> Optional[dict]:
        path = Path(file_path)
        if not path.is_file() or path.suffix.lower() not in RoadImageProcessor._supported_image_extensions():
            return None

        try:
            with Image.open(path) as img:
                width, height = img.size
        except Exception:
            return None

        return {
            'path': str(path),
            'name': path.name,
            'folder': str(path.parent),
            'size': f"{width}x{height}"
        }

    @staticmethod
    def scan_image_files(root_dir: str, include_subfolders: bool = True) -> List[dict]:
        """Busca imagenes comunes sin depender del patron exportado por el programa."""
        if not root_dir or not os.path.isdir(root_dir):
            return []

        root_path = Path(root_dir)
        iterator = root_path.rglob("*") if include_subfolders else root_path.glob("*")
        records = []

        for file_path in iterator:
            record = RoadImageProcessor._image_record(str(file_path))
            if record:
                records.append(record)

        return sorted(records, key=lambda item: item['path'].lower())

    @staticmethod
    def _natural_sort_key(value):
        return [
            int(part) if part.isdigit() else part.lower()
            for part in re.split(r'(\d+)', str(value))
        ]

    @staticmethod
    def _extract_lane_id(prefix: str, group_keyword: str = "") -> Optional[str]:
        match = re.search(r'(?i)(?:^|_)CARRIL[_\s-]*(?P<lane>[A-Za-z0-9]+)(?=_|$)', prefix)
        if match:
            return match.group('lane')

        keyword = (group_keyword or "").strip()
        if keyword:
            match = re.search(re.escape(keyword), prefix, flags=re.IGNORECASE)
            if match:
                nomenclature = prefix[:match.start()].strip('_ -')
                return nomenclature or None

        return None

    @staticmethod
    def _prefix_group_key(prefix: str, group_keyword: str = "") -> Tuple[str, bool]:
        """Devuelve la clave de grupo. Si hay palabra, agrupa por esa parte del nombre."""
        keyword = (group_keyword or "").strip()
        if not keyword:
            return prefix, False

        if "carril" in keyword.lower():
            clean = re.sub(r'(?i)(^|_)CARRIL[_\s-]*[A-Za-z0-9]+(?=_|$)', r'\1', prefix)
            clean = re.sub(r'_+', '_', clean).strip('_ ')
            return (clean or prefix), True

        match = re.search(re.escape(keyword), prefix, flags=re.IGNORECASE)
        if not match:
            return prefix, False

        key = prefix[match.start():].strip('_ ')
        return (key or prefix), True

    @staticmethod
    def scan_tile_groups(root_dir: str, include_subfolders: bool = True,
                         group_keyword: str = "") -> List[dict]:
        """Busca tiles generados por este programa y los agrupa por carpeta/prefijo."""
        if not root_dir or not os.path.isdir(root_dir):
            return []

        root_path = Path(root_dir)
        pattern = re.compile(r"^(?P<prefix>.+)_(?P<index>\d{6})$")
        valid_tile_exts = {".png", ".tif", ".tiff"}
        valid_image_exts = RoadImageProcessor._supported_image_extensions()
        groups = {}
        keyword = (group_keyword or "").strip()

        iterator = root_path.rglob("*") if include_subfolders else root_path.glob("*")
        for file_path in iterator:
            if not file_path.is_file() or file_path.suffix.lower() not in valid_image_exts:
                continue

            match = pattern.match(file_path.stem)
            if match and file_path.suffix.lower() in valid_tile_exts:
                prefix = match.group("prefix")
                index = int(match.group("index"))
            elif keyword and re.search(re.escape(keyword), file_path.stem, flags=re.IGNORECASE):
                prefix = file_path.stem
                index = 0
            else:
                continue

            folder = str(file_path.parent)
            group_key, grouped_by_keyword = RoadImageProcessor._prefix_group_key(prefix, keyword)
            key_folder = str(root_path) if grouped_by_keyword else folder
            key = (key_folder, group_key)
            lane_id = RoadImageProcessor._extract_lane_id(prefix, keyword)
            groups.setdefault(key, {
                'folder': key_folder,
                'prefix': group_key,
                'tiles': [],
                'folders': set(),
                'source_prefixes': set(),
                'lanes': set(),
                'grouped_by_keyword': grouped_by_keyword
            })
            groups[key]['tiles'].append({
                'index': index,
                'path': str(file_path),
                'folder': folder,
                'prefix': prefix,
                'lane': lane_id
            })
            groups[key]['folders'].add(folder)
            groups[key]['source_prefixes'].add(prefix)
            if lane_id:
                groups[key]['lanes'].add(lane_id)

        result = []
        for group in groups.values():
            raw_tiles = sorted(
                group['tiles'],
                key=lambda item: (
                    item['index'],
                    RoadImageProcessor._natural_sort_key(item.get('lane') or ""),
                    item['path'].lower()
                )
            )
            if group.get('grouped_by_keyword') and len(group.get('lanes', [])) > 1:
                lane_order = sorted(group['lanes'], key=RoadImageProcessor._natural_sort_key)
                index_order = sorted({item['index'] for item in raw_tiles})
                by_index_lane = {}
                for item in raw_tiles:
                    by_index_lane.setdefault((item['index'], item.get('lane')), []).append(item['path'])

                tiles = []
                for tile_index in index_order:
                    for lane_id in lane_order:
                        lane_paths = by_index_lane.get((tile_index, lane_id), [])
                        if lane_paths:
                            for lane_path in sorted(lane_paths, key=str.lower):
                                tiles.append((tile_index, lane_path))
                        else:
                            tiles.append((tile_index, None))
                auto_columns = len(lane_order)
            else:
                lane_order = []
                tiles = [(item['index'], item['path']) for item in raw_tiles]
                auto_columns = 0

            paths = [path for _, path in tiles]
            real_paths = [path for path in paths if path]
            if not paths:
                continue

            tile_size = ""
            try:
                with Image.open(real_paths[0]) as img:
                    tile_size = f"{img.size[0]}x{img.size[1]}"
            except Exception:
                tile_size = "N/D"

            display_folder = group['folder']
            if len(group.get('folders', [])) == 1:
                display_folder = next(iter(group['folders']))

            rel_folder = os.path.relpath(display_folder, root_dir)
            if group.get('grouped_by_keyword'):
                display_name = group['prefix']
            elif rel_folder == "." or os.path.basename(display_folder) == group['prefix']:
                display_name = group['prefix']
            else:
                display_name = os.path.join(rel_folder, group['prefix'])

            # Leer metadata del grid si existe
            grid_columns = 0
            grid_rows = 0
            if auto_columns > 0:
                grid_columns = auto_columns
            else:
                metadata_path = os.path.join(display_folder, '_tile_info.json')
                try:
                    if os.path.isfile(metadata_path):
                        with open(metadata_path, 'r', encoding='utf-8') as mf:
                            meta = json.load(mf)
                        grid_columns = int(meta.get('grid_columns', 0))
                        grid_rows = int(meta.get('grid_rows', 0))
                except Exception:
                    pass

            output_name = f"{RoadImageProcessor._safe_filename(display_name)}_join.png"
            result.append({
                'display_name': display_name,
                'folder': display_folder,
                'prefix': group['prefix'],
                'tile_count': len(real_paths),
                'cell_count': len(paths),
                'tile_size': tile_size,
                'tile_items': tiles,
                'tile_indices': [index for index, _ in tiles],
                'paths': paths,
                'output_name': output_name,
                'grid_columns': grid_columns,
                'grid_rows': grid_rows,
                'grouped_by_keyword': group.get('grouped_by_keyword', False),
                'group_keyword': keyword,
                'lane_order': lane_order,
                'source_prefixes': sorted(group.get('source_prefixes', []), key=str.lower)
            })

        return sorted(result, key=lambda item: item['display_name'].lower())

    @staticmethod
    def build_join_batches(group: dict, start_index: int = 0, end_index: int = -1,
                           batch_size: int = 0) -> List[dict]:
        """Divide un grupo de tiles por rango e intervalo para generar uno o varios joins."""
        if group.get('tile_items'):
            tile_items = list(group['tile_items'])
        else:
            tile_items = list(enumerate(group.get('paths', [])))

        if not tile_items:
            return []

        tile_items = [
            item for _, item in sorted(
                enumerate(tile_items),
                key=lambda wrapped: (wrapped[1][0], wrapped[0])
            )
        ]
        first_index = tile_items[0][0]
        last_index = tile_items[-1][0]
        start_index = max(first_index, int(start_index))
        end_index = last_index if int(end_index) < 0 else min(last_index, int(end_index))

        if start_index > end_index:
            return []

        selected = [(idx, path) for idx, path in tile_items if start_index <= idx <= end_index]
        if not selected:
            return []

        batch_size = int(batch_size) if batch_size else 0
        if batch_size <= 0:
            chunks = [selected]
        else:
            chunks = [selected[pos:pos + batch_size] for pos in range(0, len(selected), batch_size)]

        batches = []
        base_name = RoadImageProcessor._safe_filename(group.get('display_name') or group.get('prefix') or "join")
        full_range = start_index <= first_index and end_index >= last_index

        for chunk_number, chunk in enumerate(chunks, 1):
            chunk_first = chunk[0][0]
            chunk_last = chunk[-1][0]
            paths = [path for _, path in chunk]

            if len(chunks) == 1 and full_range:
                output_name = group.get('output_name', f"{base_name}_join.png")
            else:
                output_name = f"{base_name}_{chunk_first:06d}_{chunk_last:06d}_join.png"

            batch = dict(group)
            batch.update({
                'display_name': f"{group.get('display_name', base_name)} [{chunk_first:06d}-{chunk_last:06d}]",
                'paths': paths,
                'tile_items': chunk,
                'tile_indices': [idx for idx, _ in chunk],
                'tile_count': len([path for path in paths if path]),
                'cell_count': len(paths),
                'output_name': output_name,
                'batch_number': chunk_number,
                'batch_total': len(chunks),
                'range_start': chunk_first,
                'range_end': chunk_last
            })
            batches.append(batch)

        return batches

    @staticmethod
    def join_tile_group(group: dict, output_dir: str, columns: int = 0,
                        spacing: int = 0, background=(255, 255, 255),
                        progress_callback=None) -> str:
        """Une los tiles de un grupo en una sola imagen tipo mosaico."""
        paths = group.get('paths', [])
        real_paths = [path for path in paths if path]
        if not real_paths:
            raise ValueError("El grupo no tiene tiles para juntar")

        os.makedirs(output_dir, exist_ok=True)
        columns = int(columns) if columns else 0
        spacing = max(0, int(spacing))

        if columns <= 0:
            columns = int(group.get('grid_columns') or 0)
        if columns <= 0:
            columns = max(1, math.ceil(math.sqrt(len(paths))))
        else:
            columns = min(columns, len(paths))
        rows = math.ceil(len(paths) / columns)

        sizes = []
        for path in real_paths:
            with Image.open(path) as img:
                sizes.append(img.size)

        cell_w = max(width for width, _ in sizes)
        cell_h = max(height for _, height in sizes)
        joined_w = columns * cell_w + spacing * (columns - 1)
        joined_h = rows * cell_h + spacing * (rows - 1)
        canvas = Image.new("RGB", (joined_w, joined_h), background)

        for idx, path in enumerate(paths):
            row = idx // columns
            col = idx % columns
            x = col * (cell_w + spacing)
            y = row * (cell_h + spacing)

            if not path:
                continue

            with Image.open(path) as img:
                if img.mode in ("RGBA", "LA"):
                    tile = img.convert("RGBA")
                    paste_x = x + (cell_w - tile.size[0]) // 2
                    paste_y = y + (cell_h - tile.size[1]) // 2
                    canvas.paste(tile.convert("RGB"), (paste_x, paste_y), tile.getchannel("A"))
                else:
                    tile = img.convert("RGB")
                    paste_x = x + (cell_w - tile.size[0]) // 2
                    paste_y = y + (cell_h - tile.size[1]) // 2
                    canvas.paste(tile, (paste_x, paste_y))

            if progress_callback and (idx + 1 == len(paths) or (idx + 1) % 25 == 0):
                progress_callback(f"    {idx + 1}/{len(paths)} tiles unidos")

        output_path = os.path.join(output_dir, group.get('output_name', 'join.png'))
        canvas.save(output_path, "PNG", compress_level=6)
        return output_path


class RoadProcessorGUI:
    """Interfaz gráfica principal MEJORADA"""
    
    def __init__(self):
        if DRAG_DROP_AVAILABLE:
            self.root = TkinterDnD.Tk()
        else:
            self.root = tk.Tk()
        
        self.colors = MACOS_COLORS
        self.root.title("Recorte de Imágenes - YOLO")
        self.root.geometry("1400x950")
        self.root.minsize(1200, 800)
        self.root.configure(bg=self.colors['bg'])
        
        self.imagenes = []
        self.configuraciones = {}
        self.output_dir = tk.StringVar(value="")
        
        # Configuración global por defecto CON X/Y
        self.tile_size_x_global = tk.IntVar(value=820)
        self.tile_size_y_global = tk.IntVar(value=820)
        self.overlap_global = tk.IntVar(value=5)
        
        self.use_polygon = tk.BooleanVar(value=False)
        self.use_gpu = tk.BooleanVar(value=GPU_AVAILABLE)
        self.export_format = tk.StringVar(value="PNG")
        
        # Variables de zoom y preview
        self.show_grid = tk.BooleanVar(value=True)
        self.show_overlap = tk.BooleanVar(value=True)
        self.skip_last_tile = tk.BooleanVar(value=False)
        self.zoom_level = tk.DoubleVar(value=1.0)
        self.show_pixel_info = tk.BooleanVar(value=True)
        
        self.carpeta_por_imagen = tk.BooleanVar(value=True)  # True=subcarpeta por imagen, False=todo en una
        self.manual_angle = tk.DoubleVar(value=0.0)
        self.current_preview_filepath = None
        self.current_preview_image = None
        self.preview_offset_x = 0
        self.preview_offset_y = 0

        # Join de tiles generados
        self.join_input_dir = tk.StringVar(value="")
        self.join_output_dir = tk.StringVar(value="")
        self.join_columns = tk.IntVar(value=1)  # 1 = vertical (pavimento)
        self.join_spacing = tk.IntVar(value=0)
        self.join_start_index = tk.IntVar(value=0)
        self.join_end_index = tk.IntVar(value=-1)
        self.join_batch_size = tk.IntVar(value=0)
        self.join_include_subfolders = tk.BooleanVar(value=True)
        self.join_group_keyword = tk.StringVar(value="")
        self.join_groups = []
        self.join_free_images = []
        self.join_free_preview_photo = None
        self.join_processing = False
        # Mosaic preview state (visor libre)
        self.join_mosaic_pil = None
        self.join_mosaic_photo = None
        self.join_mosaic_zoom = 1.0
        self.join_mosaic_offset_x = 0
        self.join_mosaic_offset_y = 0
        self.join_mosaic_drag_x = 0
        self.join_mosaic_drag_y = 0
        # Auto-export mosaic viewer state
        self.auto_mosaic_pil = None
        self.auto_mosaic_photo = None
        self.auto_mosaic_zoom = 1.0
        self.auto_mosaic_drag_x = 0
        self.auto_mosaic_drag_y = 0
        self.auto_tile_records = []  # list of {'path','name','size','folder','index'}
        self.auto_tile_records_full = []  # copia sin filtrar
        self.auto_tile_filter_text = ''  # texto de busqueda
        self.auto_tile_filter_size = 'Todos'  # filtro por tamaño
        self.auto_tile_filter_folder = 'Todos'  # filtro por carpeta
        self.auto_tile_sort_criteria = 'Original'  # criterio de orden activo
        self.auto_tile_sort_ascending = True  # dirección de orden
        self.auto_selected_group_idx = None
        
        self.processing = False
        self.should_stop = False
        self._suppressing_trace = False
        
        self._setup_styles()
        self._setup_ui()
        self._load_config()

        # Auto-copiar X a Y cuando cambie X y auto-actualizar recortes
        self.tile_size_x_global.trace_add('write', self._on_tile_x_changed)
        self.overlap_global.trace_add('write', self._on_config_changed)
    
    def _setup_styles(self):
        global UI_FONT_FAMILY, UI_MONO_FONT_FAMILY

        UI_FONT_FAMILY = _pick_font_family(
            self.root,
            ('SF Pro Display', 'SF Pro Text', 'Helvetica Neue', 'Segoe UI', 'Arial'),
            'Arial'
        )
        UI_MONO_FONT_FAMILY = _pick_font_family(
            self.root,
            ('SF Mono', 'JetBrains Mono', 'Cascadia Code', 'Consolas', 'Courier New'),
            'Consolas'
        )

        style = ttk.Style()
        style.theme_use('clam')

        self.default_ui_font = tkfont.Font(root=self.root, family=UI_FONT_FAMILY, size=10)
        self.root.option_add('*Font', self.default_ui_font)

        style.configure('.', background=self.colors['surface'], foreground=self.colors['text'],
                        font=(UI_FONT_FAMILY, 10))
        style.configure('TFrame', background=self.colors['surface'])
        style.configure('TLabel', background=self.colors['surface'], foreground=self.colors['text'])
        style.configure('TLabelframe', background=self.colors['surface'], borderwidth=1, relief='solid')
        style.configure('TLabelframe.Label', background=self.colors['surface'],
                        foreground=self.colors['text'], font=(UI_FONT_FAMILY, 10, 'bold'))

        style.configure('Title.TLabel', background=self.colors['surface'],
                        font=(UI_FONT_FAMILY, 17, 'bold'), foreground=self.colors['text'])
        style.configure('Subtitle.TLabel', background=self.colors['surface'],
                        font=(UI_FONT_FAMILY, 11, 'bold'), foreground=self.colors['text'])
        style.configure('Info.TLabel', background=self.colors['surface'],
                        font=(UI_FONT_FAMILY, 10), foreground=self.colors['muted'])
        style.configure('Footer.TLabel', background=self.colors['surface'],
                        font=(UI_FONT_FAMILY, 10, 'bold'), foreground=self.colors['text'])
        style.configure('Author.TLabel', background=self.colors['surface'],
                        font=(UI_FONT_FAMILY, 9, 'bold'), foreground=self.colors['accent'])
        style.configure('Success.TLabel', background=self.colors['surface'],
                        font=(UI_FONT_FAMILY, 10, 'bold'), foreground=self.colors['accent'])
        style.configure('Warning.TLabel', background=self.colors['surface'],
                        font=(UI_FONT_FAMILY, 10, 'bold'), foreground=self.colors['warning'])
        style.configure('Pixel.TLabel', background=self.colors['surface'],
                        font=(UI_MONO_FONT_FAMILY, 9), foreground=self.colors['accent'])
        style.configure('TButton', background='#e9f1ff', foreground=self.colors['accent'],
                        padding=(14, 8), borderwidth=0, relief='flat',
                        font=(UI_FONT_FAMILY, 10, 'bold'))
        style.map('TButton',
                  background=[('disabled', self.colors['panel']),
                              ('pressed', '#d4e5ff'),
                              ('active', '#dceaff')],
                  foreground=[('disabled', self.colors['muted'])])

        style.configure('Action.TButton', background=self.colors['accent'], foreground='#ffffff',
                        padding=(16, 9), borderwidth=0, relief='flat',
                        font=(UI_FONT_FAMILY, 10, 'bold'))
        style.map('Action.TButton',
                  background=[('disabled', '#bfdcff'),
                              ('pressed', self.colors['accent_hover']),
                              ('active', self.colors['accent_hover'])],
                  foreground=[('disabled', '#eef6ff')])

        style.configure('Secondary.TButton', background=self.colors['accent_soft'],
                        foreground=self.colors['accent'], padding=(14, 8), borderwidth=0,
                        relief='flat', font=(UI_FONT_FAMILY, 10, 'bold'))
        style.map('Secondary.TButton',
                  background=[('disabled', self.colors['panel']),
                              ('pressed', '#d5e8ff'),
                              ('active', '#dff0ff')],
                  foreground=[('disabled', self.colors['muted'])])

        style.configure('TEntry', fieldbackground=self.colors['surface_alt'],
                        foreground=self.colors['text'], borderwidth=0, padding=8)
        style.configure('TSpinbox', fieldbackground=self.colors['surface_alt'],
                        foreground=self.colors['text'], borderwidth=0, padding=6, arrowsize=13)
        style.configure('TCheckbutton', background=self.colors['surface'], foreground=self.colors['text'])
        style.configure('TRadiobutton', background=self.colors['surface'], foreground=self.colors['text'])

        style.configure('TNotebook', background=self.colors['bg'], borderwidth=0)
        style.configure('TNotebook.Tab', background=self.colors['surface_alt'],
                        foreground=self.colors['muted'], padding=(18, 10),
                        font=(UI_FONT_FAMILY, 10, 'bold'), borderwidth=0)
        style.map('TNotebook.Tab',
                  background=[('selected', self.colors['surface']),
                              ('active', self.colors['accent_soft'])],
                  foreground=[('selected', self.colors['text']),
                              ('active', self.colors['accent'])])

        style.configure('Treeview', background=self.colors['surface'],
                        fieldbackground=self.colors['surface'], foreground=self.colors['text'],
                        rowheight=30, borderwidth=0, font=(UI_FONT_FAMILY, 10))
        style.map('Treeview',
                  background=[('selected', self.colors['selection'])],
                  foreground=[('selected', self.colors['text'])])
        style.configure('Treeview.Heading', background='#dceaff',
                        foreground=self.colors['accent'], borderwidth=0,
                        font=(UI_FONT_FAMILY, 10, 'bold'), padding=(10, 8))
        style.map('Treeview.Heading',
                  background=[('active', '#cfe3ff'), ('pressed', '#c7dcff')],
                  foreground=[('active', self.colors['accent']), ('pressed', self.colors['accent'])])

        style.configure('Green.Horizontal.TProgressbar',
                        troughcolor=self.colors['panel'],
                        background=self.colors['accent'],
                        thickness=14,
                        borderwidth=0)

    def _set_save_rotation_button_state(self, enabled=False, angle=None):
        if not hasattr(self, 'btn_save_rotation'):
            return

        if not enabled:
            _style_flat_button(self.btn_save_rotation, 'neutral')
            self.btn_save_rotation.config(state=tk.DISABLED, text="Guardar rotación", cursor='arrow')
            return

        self.btn_save_rotation.config(state=tk.NORMAL, cursor='hand2')
        if angle is None:
            _style_flat_button(self.btn_save_rotation, 'warning')
            self.btn_save_rotation.config(text="Guardar rotación")
        else:
            _style_flat_button(self.btn_save_rotation, 'success')
            self.btn_save_rotation.config(text=f"Guardado ({angle:.2f}°)")
    
    def _setup_ui(self):
        header_frame = ttk.Frame(self.root, padding=(16, 10))
        header_frame.pack(fill=tk.X, padx=14, pady=(10, 6))

        ttk.Label(header_frame, text="Recorte de Imágenes - YOLO",
                 style='Title.TLabel').pack(side=tk.LEFT)

        info_text = "Preparación de conjuntos de datos y generación de tiles"
        ttk.Label(header_frame, text=info_text, style='Info.TLabel').pack(side=tk.LEFT, padx=(18, 0))
        ttk.Label(
            header_frame,
            text="Bach. Miguel Bernardino Quispe Arias  |  Bach. Briza Edith Catachura Aycaya",
            style='Author.TLabel'
        ).pack(side=tk.RIGHT)

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 8))

        tab_imagenes = ttk.Frame(notebook, padding=12)
        notebook.add(tab_imagenes, text="📁 1. Imágenes")
        self._setup_images_tab(tab_imagenes)

        tab_polygon = ttk.Frame(notebook, padding=12)
        notebook.add(tab_polygon, text="🎯 2. Vista Previa")
        self._setup_polygon_tab(tab_polygon)

        tab_config = ttk.Frame(notebook, padding=12)
        notebook.add(tab_config, text="⚙️ 3. Configuración")
        self._setup_config_tab(tab_config)

        tab_process = ttk.Frame(notebook, padding=12)
        notebook.add(tab_process, text="▶️ 4. Procesar")
        self._setup_process_tab(tab_process)

        tab_join = ttk.Frame(notebook, padding=12)
        notebook.add(tab_join, text="5. Join")
        self._setup_join_tab(tab_join)

        footer_frame = ttk.Frame(self.root, padding=(18, 14))
        footer_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=14, pady=(0, 14))

        ttk.Button(footer_frame, text="❌ Salir", 
                  command=self._on_closing).pack(side=tk.RIGHT, padx=5)
        
        self.btn_process = ttk.Button(footer_frame, text="▶️ Iniciar Procesamiento",
                                     style='Action.TButton',
                                     command=self._start_processing, state=tk.DISABLED)
        self.btn_process.pack(side=tk.RIGHT, padx=5)

        self.btn_process_single = ttk.Button(footer_frame, text="▶ Exportar Imagen Seleccionada",
                                            style='Secondary.TButton',
                                            command=self._start_processing_single, state=tk.DISABLED)
        self.btn_process_single.pack(side=tk.RIGHT, padx=5)
    
    def _setup_images_tab(self, parent):
        top_frame = ttk.Frame(parent)
        top_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(top_frame, text="Selecciona las imágenes a procesar:",
                 style='Subtitle.TLabel').pack(side=tk.LEFT)
        
        btn_frame = ttk.Frame(top_frame)
        btn_frame.pack(side=tk.RIGHT)
        
        ttk.Button(btn_frame, text="➕ Agregar Archivos", 
                  command=self._add_files).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="📁 Agregar Carpeta", 
                  command=self._add_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="❌ Borrar Imagen",
                  command=self._remove_selected_image).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="🗑️ Limpiar Todo",
                  command=self._clear_images).pack(side=tk.LEFT, padx=2)
        
        # Layout redimensionable: lista (izq) + vista previa (der)
        paned = tk.PanedWindow(parent, orient=tk.HORIZONTAL,
                               sashwidth=8, sashrelief=tk.FLAT, bg=self.colors['panel'],
                               bd=0, relief=tk.FLAT, showhandle=False)
        paned.pack(fill=tk.BOTH, expand=True)

        # Panel izquierdo - Lista de imágenes
        list_frame = ttk.LabelFrame(paned, text="Imágenes Cargadas", padding=10)

        tree_scroll = ttk.Scrollbar(list_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree_images = ttk.Treeview(list_frame,
                                       columns=('Nro', 'Nombre', 'Tamaño', 'Config', 'Ruta'),
                                       show='headings',
                                       yscrollcommand=tree_scroll.set)

        self.tree_images.heading('Nro', text='#')
        self.tree_images.heading('Nombre', text='Nombre')
        self.tree_images.heading('Tamaño', text='Dimensiones')
        self.tree_images.heading('Config', text='Configuración')
        self.tree_images.heading('Ruta', text='Ruta')

        self.tree_images.column('Nro', width=40, anchor=tk.CENTER)
        self.tree_images.column('Nombre', width=200)
        self.tree_images.column('Tamaño', width=120, anchor=tk.CENTER)
        self.tree_images.column('Config', width=150, anchor=tk.CENTER)
        self.tree_images.column('Ruta', width=350)

        self.tree_images.pack(fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.tree_images.yview)

        self.tree_images.bind('<<TreeviewSelect>>', self._on_image_tree_select)

        if DRAG_DROP_AVAILABLE:
            drop_label = ttk.Label(list_frame,
                                  text="💡 Arrastra archivos aquí",
                                  style='Info.TLabel')
            drop_label.pack(pady=5)

            self.tree_images.drop_target_register(DND_FILES)
            self.tree_images.dnd_bind('<<Drop>>', self._on_drop)

        paned.add(list_frame, stretch='always')

        # Panel derecho - Vista previa (redimensionable arrastrando el divisor)
        preview_outer = ttk.Frame(paned)

        preview_frame = ttk.LabelFrame(preview_outer, text="Vista Previa (arrastrar divisor para ampliar)", padding=5)
        preview_frame.pack(fill=tk.BOTH, expand=True)

        self.img_preview_canvas = tk.Canvas(preview_frame, bg=self.colors['canvas'])
        self.img_preview_canvas.pack(fill=tk.BOTH, expand=True)
        _style_canvas_widget(self.img_preview_canvas, self.colors['canvas'])
        self.img_preview_canvas.bind('<Configure>', self._on_preview1_resize)
        self.img_preview_photo = None
        self._preview1_filepath = None  # filepath de la imagen mostrada actualmente

        self.img_preview_info = ttk.Label(preview_frame, text="", style='Info.TLabel')
        self.img_preview_info.pack(pady=(3, 0))

        paned.add(preview_outer, stretch='never', width=300)
    
    def _setup_config_tab(self, parent):
        """Tab de configuración con TILES X/Y separados"""
        left_frame = ttk.LabelFrame(parent, text="Configuración Global (por defecto)", padding=15)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        ttk.Label(left_frame, text="📂 Directorio de Salida:",
                 style='Subtitle.TLabel').grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 5))
        
        ttk.Entry(left_frame, textvariable=self.output_dir, 
                 width=40).grid(row=1, column=0, columnspan=2, sticky=tk.EW, pady=(0, 10))
        ttk.Button(left_frame, text="📁 Seleccionar", 
                  command=self._select_output_dir).grid(row=1, column=2, padx=(5, 0))
        
        ttk.Separator(left_frame, orient=tk.HORIZONTAL).grid(row=2, column=0, columnspan=3, sticky=tk.EW, pady=10)
        
        # TILES X/Y
        ttk.Label(left_frame, text="🔧 Configuración de Tiles (Global):",
                 style='Subtitle.TLabel').grid(row=3, column=0, columnspan=3, sticky=tk.W)
        
        ttk.Label(left_frame, text="Ancho X (px):").grid(row=4, column=0, sticky=tk.W, pady=5)
        ttk.Spinbox(left_frame, from_=256, to=2048, increment=64,
                   textvariable=self.tile_size_x_global, width=15).grid(row=4, column=1, sticky=tk.W)
        
        ttk.Label(left_frame, text="Alto Y (px):").grid(row=5, column=0, sticky=tk.W, pady=5)
        ttk.Spinbox(left_frame, from_=256, to=2048, increment=64,
                   textvariable=self.tile_size_y_global, width=15).grid(row=5, column=1, sticky=tk.W)
        
        ttk.Button(left_frame, text="🔄 Igualar", 
                  command=self._equalize_global_tiles).grid(row=4, column=2, rowspan=2, padx=5)
        
        ttk.Label(left_frame, text="Solapamiento (px):").grid(row=6, column=0, sticky=tk.W, pady=5)
        ttk.Spinbox(left_frame, from_=0, to=200, increment=5,
                   textvariable=self.overlap_global, width=15).grid(row=6, column=1, sticky=tk.W)
        
        ttk.Separator(left_frame, orient=tk.HORIZONTAL).grid(row=7, column=0, columnspan=3, sticky=tk.EW, pady=10)

        ttk.Button(left_frame, text="💾 Aplicar Global a Todas",
                  command=self._apply_global_to_all).grid(row=8, column=0, columnspan=3, pady=10)

        ttk.Separator(left_frame, orient=tk.HORIZONTAL).grid(row=9, column=0, columnspan=3, sticky=tk.EW, pady=10)
        
        # Organización de carpetas
        ttk.Separator(left_frame, orient=tk.HORIZONTAL).grid(row=10, column=0, columnspan=3, sticky=tk.EW, pady=10)
        ttk.Label(left_frame, text="📂 Organización de salida:",
                 style='Subtitle.TLabel').grid(row=11, column=0, columnspan=3, sticky=tk.W)

        ttk.Radiobutton(left_frame, text="Una subcarpeta por imagen",
                       variable=self.carpeta_por_imagen, value=True).grid(row=12, column=0, columnspan=3, sticky=tk.W, pady=2)
        ttk.Radiobutton(left_frame, text="Todas las imágenes en una sola carpeta",
                       variable=self.carpeta_por_imagen, value=False).grid(row=13, column=0, columnspan=3, sticky=tk.W, pady=2)

        # Frame derecho
        right_frame = ttk.LabelFrame(parent, text="⚙️ Configuración Individual", padding=15)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        tree_scroll2 = ttk.Scrollbar(right_frame)
        tree_scroll2.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree_config = ttk.Treeview(right_frame,
                                       columns=('Nro', 'Imagen', 'TileX', 'TileY', 'Ovlp', 'Recortes'),
                                       show='headings',
                                       yscrollcommand=tree_scroll2.set)

        self.tree_config.heading('Nro', text='#')
        self.tree_config.heading('Imagen', text='Imagen')
        self.tree_config.heading('TileX', text='X')
        self.tree_config.heading('TileY', text='Y')
        self.tree_config.heading('Ovlp', text='Overlap')
        self.tree_config.heading('Recortes', text='Recortes')

        self.tree_config.column('Nro', width=40, anchor=tk.CENTER)
        self.tree_config.column('Imagen', width=200)
        self.tree_config.column('TileX', width=60, anchor=tk.CENTER)
        self.tree_config.column('TileY', width=60, anchor=tk.CENTER)
        self.tree_config.column('Ovlp', width=70, anchor=tk.CENTER)
        self.tree_config.column('Recortes', width=80, anchor=tk.CENTER)
        
        self.tree_config.pack(fill=tk.BOTH, expand=True)
        tree_scroll2.config(command=self.tree_config.yview)

        self.tree_config.bind('<<TreeviewSelect>>', self._on_config_tree_select)

        btn_config_frame = ttk.Frame(right_frame)
        btn_config_frame.pack(pady=10)
        
        ttk.Button(btn_config_frame, text="✏️ Editar", 
                  command=self._edit_individual_config).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_config_frame, text="📋 Copiar Global", 
                  command=self._copy_from_global).pack(side=tk.LEFT, padx=5)
    
    def _equalize_global_tiles(self):
        """Iguala Y al X"""
        self.tile_size_y_global.set(self.tile_size_x_global.get())

    def _on_tile_x_changed(self, *args):
        """Auto-copia el valor de Ancho X a Alto Y y actualiza recortes"""
        if self._suppressing_trace:
            return
        try:
            self._suppressing_trace = True
            self.tile_size_y_global.set(self.tile_size_x_global.get())
            self._suppressing_trace = False
            self._refresh_all_recortes()
        except:
            self._suppressing_trace = False

    def _on_config_changed(self, *args):
        """Actualiza recortes cuando cambian parámetros globales"""
        try:
            self._refresh_all_recortes()
        except:
            pass

    def _refresh_all_recortes(self):
        """Actualiza la columna Recortes de todas las imágenes en Configuración Individual"""
        if self._suppressing_trace:
            return
        for item_id in self.tree_config.get_children():
            item_vals = self.tree_config.item(item_id)['values']
            nro = item_vals[0]
            nombre = item_vals[1]
            filepath = None
            for fp in self.imagenes:
                if os.path.basename(fp) == nombre:
                    filepath = fp
                    break
            if filepath:
                config = self.configuraciones[filepath]
                num_recortes = self._calcular_num_recortes(filepath)
                self.tree_config.item(item_id,
                                     values=(nro, nombre,
                                            config.get('tile_size_x', self.tile_size_x_global.get()),
                                            config.get('tile_size_y', self.tile_size_y_global.get()),
                                            config.get('overlap', self.overlap_global.get()),
                                            num_recortes))

    def _calcular_num_recortes(self, filepath):
        """Calcula la cantidad de recortes (tiles) que se generarán para una imagen"""
        try:
            config = self.configuraciones.get(filepath, {})
            tile_x = config.get('tile_size_x', self.tile_size_x_global.get())
            tile_y = config.get('tile_size_y', self.tile_size_y_global.get())
            overlap = config.get('overlap', self.overlap_global.get())

            # Usar dimensiones de preview procesada si están disponibles
            w = config.get('_preview_w')
            h = config.get('_preview_h')
            if w is None or h is None:
                img = Image.open(filepath)
                w, h = img.size
                img.close()

            step_x = tile_x - overlap
            step_y = tile_y - overlap
            if step_x <= 0 or step_y <= 0:
                return 0

            num_x = math.ceil((w - overlap) / step_x)
            num_y = math.ceil((h - overlap) / step_y)
            return num_x * num_y
        except:
            return 0
    
    def _setup_polygon_tab(self, parent):
        """Tab REORGANIZADO con preview arriba"""
        # LAYOUT MEJORADO: Preview arriba, controles abajo
        
        # Frame superior - VISTA PREVIA
        preview_container = ttk.LabelFrame(parent, text="🎯 Vista Previa Interactiva", padding=10)
        preview_container.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Info
        info_frame = ttk.Frame(preview_container)
        info_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(info_frame,
                 text="📐 Tiles rectangulares • 🔍 Zoom • 💡 Info píxeles • ⚡ Solapamiento visible",
                 style='Success.TLabel').pack(side=tk.LEFT)

        self.pixel_info_label = ttk.Label(info_frame,
                                         text="",
                                         style='Pixel.TLabel')
        self.pixel_info_label.pack(side=tk.RIGHT, padx=10)

        # PanedWindow horizontal: preview (izq) + miniatura resultado (der)
        # El usuario puede arrastrar el divisor para redistribuir espacio
        preview_pane = tk.PanedWindow(preview_container, orient=tk.HORIZONTAL,
                                      sashwidth=8, sashrelief=tk.FLAT, bg=self.colors['panel'],
                                      bd=0, relief=tk.FLAT, showhandle=False)
        preview_pane.pack(fill=tk.BOTH, expand=True)

        # === Panel izquierdo: Canvas con scroll ===
        canvas_container = ttk.Frame(preview_pane)

        h_scroll = ttk.Scrollbar(canvas_container, orient=tk.HORIZONTAL)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        v_scroll = ttk.Scrollbar(canvas_container, orient=tk.VERTICAL)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.preview_canvas = tk.Canvas(canvas_container, bg=self.colors['canvas'],
                                       xscrollcommand=h_scroll.set,
                                       yscrollcommand=v_scroll.set)
        self.preview_canvas.pack(fill=tk.BOTH, expand=True)
        _style_canvas_widget(self.preview_canvas, self.colors['canvas'])

        h_scroll.config(command=self.preview_canvas.xview)
        v_scroll.config(command=self.preview_canvas.yview)

        # Bindings
        self.preview_canvas.bind('<MouseWheel>', self._on_mousewheel)
        self.preview_canvas.bind('<Shift-MouseWheel>', self._on_shift_mousewheel)
        self.preview_canvas.bind('<Control-MouseWheel>', self._on_ctrl_mousewheel)
        self.preview_canvas.bind('<Motion>', self._on_mouse_motion)
        self.preview_canvas.bind('<ButtonPress-1>', self._on_canvas_click)
        self.preview_canvas.bind('<B1-Motion>', self._on_canvas_drag)

        self.preview_info_label = ttk.Label(canvas_container,
                                           text="",
                                           style='Info.TLabel')
        self.preview_info_label.pack(pady=2)

        preview_pane.add(canvas_container, stretch='always')

        # === Panel derecho: Miniatura imagen final ===
        thumb_outer = ttk.Frame(preview_pane)

        thumb_frame = ttk.LabelFrame(thumb_outer, text="Imagen Final", padding=5)
        thumb_frame.pack(fill=tk.BOTH, expand=True)

        self.thumbnail_canvas = tk.Canvas(thumb_frame, bg=self.colors['canvas'], width=280)
        self.thumbnail_canvas.pack(fill=tk.BOTH, expand=True)
        _style_canvas_widget(self.thumbnail_canvas, self.colors['canvas'])
        self.thumbnail_photo = None

        self.thumbnail_size_label = ttk.Label(thumb_frame, text="", style='Info.TLabel')
        self.thumbnail_size_label.pack(pady=(3, 0))

        preview_pane.add(thumb_outer, stretch='never', width=300)
        
        # Frame inferior - CONTROLES
        controls_container = ttk.Frame(parent)
        controls_container.pack(fill=tk.X)
        
        # Columna izquierda - Polígonos y lista
        left_col = ttk.Frame(controls_container)
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        poly_frame = ttk.LabelFrame(left_col, text="🔷 Polígonos", padding=10)
        poly_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Checkbutton(poly_frame, text="Activar recorte por polígono", 
                       variable=self.use_polygon).pack(anchor=tk.W)
        
        tree_scroll = ttk.Scrollbar(poly_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree_polygons = ttk.Treeview(poly_frame,
                                         columns=('Nro', 'Imagen', 'Polígono', 'Rotación'),
                                         show='headings',
                                         height=6,
                                         yscrollcommand=tree_scroll.set)

        self.tree_polygons.heading('Nro', text='#')
        self.tree_polygons.heading('Imagen', text='Imagen')
        self.tree_polygons.heading('Polígono', text='Polígono')
        self.tree_polygons.heading('Rotación', text='Rot.')

        self.tree_polygons.column('Nro', width=40, anchor='center')
        self.tree_polygons.column('Imagen', width=200)
        self.tree_polygons.column('Polígono', width=120)
        self.tree_polygons.column('Rotación', width=60, anchor='center')
        
        self.tree_polygons.pack(fill=tk.BOTH, expand=True, pady=5)
        tree_scroll.config(command=self.tree_polygons.yview)
        
        self.tree_polygons.bind('<<TreeviewSelect>>', self._on_polygon_select)
        
        btn_poly = ttk.Frame(poly_frame)
        btn_poly.pack(pady=5)
        
        ttk.Button(btn_poly, text="🔷 Definir", 
                  command=self._define_polygon).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_poly, text="⬜ Completa", 
                  command=self._use_full_area_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_poly, text="🗑️ Limpiar", 
                  command=self._clear_polygons).pack(side=tk.LEFT, padx=2)
        
        # Columna central - Rotación con SPINBOX
        center_col = ttk.LabelFrame(controls_container, text="🎯 Rotación", padding=10)
        center_col.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        self.angle_label = ttk.Label(center_col, text="0.00°", font=(UI_FONT_FAMILY, 18, 'bold'))
        self.angle_label.pack()
        
        # SPINBOX PARA AJUSTE PRECISO
        angle_spinner_frame = ttk.Frame(center_col)
        angle_spinner_frame.pack(pady=5)
        
        ttk.Label(angle_spinner_frame, text="Ajuste fino:").pack()
        
        angle_control = ttk.Frame(angle_spinner_frame)
        angle_control.pack(pady=5)
        
        ttk.Button(angle_control, text="▼", width=3,
                  command=lambda: self._adjust_angle(-0.1)).pack(side=tk.LEFT)
        
        self.angle_entry = ttk.Entry(angle_control, textvariable=self.manual_angle, 
                                     width=10, justify=tk.CENTER)
        self.angle_entry.pack(side=tk.LEFT, padx=2)
        self.angle_entry.bind('<Return>', lambda e: self._update_preview())
        
        ttk.Button(angle_control, text="▲", width=3,
                  command=lambda: self._adjust_angle(0.1)).pack(side=tk.LEFT)
        
        # Botones rápidos
        quick_frame = ttk.Frame(center_col)
        quick_frame.pack(pady=5)
        
        ttk.Button(quick_frame, text="-1°", width=5,
                  command=lambda: self._adjust_angle(-1)).pack(side=tk.LEFT, padx=1)
        ttk.Button(quick_frame, text="+1°", width=5,
                  command=lambda: self._adjust_angle(1)).pack(side=tk.LEFT, padx=1)
        ttk.Button(quick_frame, text="90°", width=5,
                  command=lambda: self._quick_rotate(90)).pack(side=tk.LEFT, padx=1)
        
        action_frame = ttk.Frame(center_col)
        action_frame.pack(pady=5)
        
        ttk.Button(action_frame, text="Auto", width=8,
                  command=self._auto_rotate).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="Reset", width=8,
                  command=self._reset_angle).pack(side=tk.LEFT, padx=2)
        
        self.btn_save_rotation = tk.Button(center_col,
                                          text="Guardar rotación",
                                          command=self._save_manual_rotation,
                                          state=tk.DISABLED)
        self.btn_save_rotation.pack(pady=10, ipadx=10, ipady=4)
        self._set_save_rotation_button_state(enabled=False)
        
        # Columna derecha - Zoom y opciones
        right_col = ttk.LabelFrame(controls_container, text="🔍 Opciones", padding=10)
        right_col.pack(side=tk.LEFT, fill=tk.Y)
        
        zoom_btns = ttk.Frame(right_col)
        zoom_btns.pack()
        
        ttk.Button(zoom_btns, text="🔍+", width=6,
                  command=lambda: self._zoom_preview(1.2)).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_btns, text="🔍-", width=6,
                  command=lambda: self._zoom_preview(0.8)).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_btns, text="1:1", width=6,
                  command=lambda: self._reset_zoom()).pack(side=tk.LEFT, padx=2)
        
        self.zoom_label = ttk.Label(right_col, text="Zoom: 100%", font=(UI_FONT_FAMILY, 10))
        self.zoom_label.pack(pady=5)
        
        ttk.Checkbutton(right_col, text="📐 Cuadrícula", 
                       variable=self.show_grid,
                       command=self._update_preview).pack(anchor=tk.W, pady=2)
        
        ttk.Checkbutton(right_col, text="⚡ Solapamiento", 
                       variable=self.show_overlap,
                       command=self._update_preview).pack(anchor=tk.W, pady=2)
        
        ttk.Checkbutton(right_col, text="💡 Info píxeles",
                       variable=self.show_pixel_info).pack(anchor=tk.W, pady=2)

        ttk.Checkbutton(right_col, text="🚫 Omitir último recorte",
                       variable=self.skip_last_tile,
                       command=self._save_skip_last_tile).pack(anchor=tk.W, pady=2)

        # Cantidad de cortes para división exacta
        cuts_frame = ttk.LabelFrame(right_col, text="✂️ Cortes exactos", padding=5)
        cuts_frame.pack(fill=tk.X, pady=(10, 2))

        self.num_cuts_x = tk.IntVar(value=2)
        self.num_cuts_y = tk.IntVar(value=2)

        ttk.Label(cuts_frame, text="Cortes X:").grid(row=0, column=0, sticky=tk.W, padx=2)
        ttk.Spinbox(cuts_frame, from_=1, to=100, increment=1,
                   textvariable=self.num_cuts_x, width=5).grid(row=0, column=1, padx=2)

        ttk.Label(cuts_frame, text="Cortes Y:").grid(row=1, column=0, sticky=tk.W, padx=2)
        ttk.Spinbox(cuts_frame, from_=1, to=100, increment=1,
                   textvariable=self.num_cuts_y, width=5).grid(row=1, column=1, padx=2)

        ttk.Button(cuts_frame, text="Calcular",
                  command=self._calcular_tile_por_cortes).grid(row=2, column=0, columnspan=2, pady=5)

        self._clear_polygon_preview()
    
    def _setup_process_tab(self, parent):
        info_frame = ttk.LabelFrame(parent, text="📋 Proceso", padding=15)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        instrucciones = """
1. Define tiles rectangulares (X/Y) globales o individuales
2. Opcionalmente, define poligonos de recorte (CON ZOOM)
3. Ajusta rotacion con precision usando spinbox (+-0.1)
4. Visualiza solapamiento y cuadricula en tiempo real
5. El procesamiento cubrira TODA la imagen sin dejar restos
        """
        ttk.Label(info_frame, text=instrucciones, justify=tk.LEFT).pack(anchor=tk.W)

        # Formato de exportacion
        fmt_frame = ttk.Frame(info_frame)
        fmt_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Label(fmt_frame, text="Formato de exportacion:").pack(side=tk.LEFT)
        ttk.Radiobutton(fmt_frame, text="PNG", variable=self.export_format,
                        value="PNG").pack(side=tk.LEFT, padx=(10, 5))
        ttk.Radiobutton(fmt_frame, text="TIFF", variable=self.export_format,
                        value="TIFF").pack(side=tk.LEFT, padx=5)

        progress_frame = ttk.LabelFrame(parent, text="Progreso", padding=15)
        progress_frame.pack(fill=tk.BOTH, expand=True)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame,
                                           variable=self.progress_var,
                                           maximum=100,
                                           mode='determinate',
                                           style='Green.Horizontal.TProgressbar')
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        self.status_text = tk.Text(progress_frame, height=12, wrap=tk.WORD,
                                   font=(UI_MONO_FONT_FAMILY, 10))
        self.status_text.pack(fill=tk.BOTH, expand=True, pady=5)
        _style_text_widget(self.status_text)
        
        status_scroll = ttk.Scrollbar(progress_frame, command=self.status_text.yview)
        status_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.status_text.config(yscrollcommand=status_scroll.set)
        
        self.summary_frame = ttk.LabelFrame(parent, text="📊 Resumen", padding=10)
        self.summary_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.summary_label = ttk.Label(self.summary_frame,
                                      text="Esperando procesamiento...",
                                      font=(UI_FONT_FAMILY, 11, 'bold'))
        self.summary_label.pack()
    
    # ==================== Join de recortes ====================
    
    def _setup_join_tab(self, parent):
        """Tab para juntar los recortes generados por el programa.
        Layout: PanedWindow horizontal a toda altura.
        Izquierda: Carpetas + Opciones + Notebook (Auto/Libre)
        Derecha: Vista previa del mosaico (toda la altura)"""

        # ====== PanedWindow principal a toda altura ======
        main_paned = tk.PanedWindow(parent, orient=tk.HORIZONTAL,
                                     sashwidth=6, sashrelief=tk.FLAT,
                                     bg=self.colors['panel'],
                                     bd=0, relief=tk.FLAT, showhandle=False)
        main_paned.pack(fill=tk.BOTH, expand=True)

        # ======== Panel izquierdo: controles ========
        left_panel = ttk.Frame(main_paned)

        folder_frame = ttk.LabelFrame(left_panel, text="Carpetas", padding=6)
        folder_frame.pack(fill=tk.X, pady=(0, 4))

        input_row = ttk.Frame(folder_frame)
        input_row.pack(fill=tk.X, pady=(0, 3))
        ttk.Label(input_row, text="Recortes:", width=10).pack(side=tk.LEFT)
        ttk.Entry(input_row, textvariable=self.join_input_dir).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(input_row, text="...", width=3, command=self._select_join_input_dir).pack(side=tk.LEFT)

        output_row = ttk.Frame(folder_frame)
        output_row.pack(fill=tk.X)
        ttk.Label(output_row, text="Salida:", width=10).pack(side=tk.LEFT)
        ttk.Entry(output_row, textvariable=self.join_output_dir).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(output_row, text="...", width=3, command=self._select_join_output_dir).pack(side=tk.LEFT)

        options_frame = ttk.LabelFrame(left_panel, text="Opciones de union", padding=6)
        options_frame.pack(fill=tk.X, pady=(0, 4))

        opt_row1 = ttk.Frame(options_frame)
        opt_row1.pack(fill=tk.X, pady=(0, 3))
        ttk.Checkbutton(opt_row1, text="Subcarpetas",
                        variable=self.join_include_subfolders).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(opt_row1, text="Col:").pack(side=tk.LEFT)
        ttk.Spinbox(opt_row1, from_=0, to=500, width=4,
                    textvariable=self.join_columns).pack(side=tk.LEFT, padx=(3, 5))
        for n in [1, 2, 3, 4, 5, 6, 7, 8]:
            ttk.Button(opt_row1, text=str(n), width=2,
                       command=lambda c=n: self.join_columns.set(c)).pack(side=tk.LEFT, padx=1)

        opt_row2 = ttk.Frame(options_frame)
        opt_row2.pack(fill=tk.X)
        ttk.Label(opt_row2, text="Sep px:").pack(side=tk.LEFT)
        ttk.Spinbox(opt_row2, from_=0, to=200, width=4,
                    textvariable=self.join_spacing).pack(side=tk.LEFT, padx=(3, 10))
        ttk.Label(opt_row2, text="Desde:").pack(side=tk.LEFT)
        ttk.Spinbox(opt_row2, from_=0, to=999999, width=6,
                    textvariable=self.join_start_index).pack(side=tk.LEFT, padx=(3, 8))
        ttk.Label(opt_row2, text="Hasta:").pack(side=tk.LEFT)
        ttk.Spinbox(opt_row2, from_=-1, to=999999, width=6,
                    textvariable=self.join_end_index).pack(side=tk.LEFT, padx=(3, 8))
        ttk.Button(opt_row2, text="Analizar grupos",
                   command=self._scan_join_groups).pack(side=tk.RIGHT)

        opt_row3 = ttk.Frame(options_frame)
        opt_row3.pack(fill=tk.X, pady=(3, 0))
        ttk.Label(opt_row3, text="Agrupar por palabra:").pack(side=tk.LEFT)
        ttk.Entry(opt_row3, textvariable=self.join_group_keyword, width=18).pack(side=tk.LEFT, padx=(3, 5))
        ttk.Button(opt_row3, text="Progresiva", width=10,
                   command=lambda: self.join_group_keyword.set("Progresiva")).pack(side=tk.LEFT, padx=1)
        ttk.Button(opt_row3, text="PCI/TRAMO", width=10,
                   command=self._use_pci_tramo_grouping).pack(side=tk.LEFT, padx=1)
        ttk.Button(opt_row3, text="CARRIL", width=7,
                   command=lambda: self.join_group_keyword.set("CARRIL")).pack(side=tk.LEFT, padx=1)
        ttk.Button(opt_row3, text="Limpiar", width=7,
                   command=lambda: self.join_group_keyword.set("")).pack(side=tk.RIGHT)

        # Notebook con pestanas Auto y Libre
        join_mode_tabs = ttk.Notebook(left_panel)
        join_mode_tabs.pack(fill=tk.BOTH, expand=True)

        auto_join_tab = ttk.Frame(join_mode_tabs, padding=4)
        free_join_tab = ttk.Frame(join_mode_tabs, padding=4)
        join_mode_tabs.add(auto_join_tab, text="Automatico exportado")
        join_mode_tabs.add(free_join_tab, text="Visor libre")

        self._setup_auto_join_content(auto_join_tab)
        self._setup_free_join_content(free_join_tab)

        main_paned.add(left_panel, stretch='always')

        # ======== Panel derecho: visor mosaico compartido (toda la altura) ========
        right_panel = ttk.Frame(main_paned)

        preview_frame = ttk.LabelFrame(right_panel, text="Vista previa del mosaico", padding=5)
        preview_frame.pack(fill=tk.BOTH, expand=True)
        preview_frame.rowconfigure(1, weight=1)
        preview_frame.columnconfigure(0, weight=1)

        mosaic_toolbar = ttk.Frame(preview_frame)
        mosaic_toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 4))

        self.btn_auto_generate_mosaic = ttk.Button(
            mosaic_toolbar, text="Vista previa (auto)",
            style='Action.TButton', command=self._generate_auto_mosaic_preview, state=tk.DISABLED
        )
        self.btn_auto_generate_mosaic.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_generate_mosaic = ttk.Button(
            mosaic_toolbar, text="Vista previa (libre)",
            style='Secondary.TButton', command=self._generate_mosaic_preview, state=tk.DISABLED
        )
        self.btn_generate_mosaic.pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(mosaic_toolbar, text="\U0001f50d+", width=3,
                   command=lambda: self._zoom_shared_mosaic(1.3)).pack(side=tk.LEFT, padx=1)
        ttk.Button(mosaic_toolbar, text="\U0001f50d-", width=3,
                   command=lambda: self._zoom_shared_mosaic(0.7)).pack(side=tk.LEFT, padx=1)
        ttk.Button(mosaic_toolbar, text="1:1", width=3,
                   command=self._reset_shared_mosaic_zoom).pack(side=tk.LEFT, padx=1)

        self.auto_mosaic_zoom_label = ttk.Label(mosaic_toolbar, text="100%",
                                                 font=(UI_FONT_FAMILY, 10, 'bold'))
        self.auto_mosaic_zoom_label.pack(side=tk.LEFT, padx=6)
        self.mosaic_zoom_label = self.auto_mosaic_zoom_label

        self.btn_auto_save_mosaic = ttk.Button(
            mosaic_toolbar, text="Confirmar y Guardar",
            style='Action.TButton', command=self._save_current_mosaic_result, state=tk.DISABLED
        )
        self.btn_auto_save_mosaic.pack(side=tk.RIGHT, padx=5)
        self.btn_save_mosaic = self.btn_auto_save_mosaic

        mosaic_canvas_frame = ttk.Frame(preview_frame)
        mosaic_canvas_frame.grid(row=1, column=0, sticky="nsew")
        mosaic_canvas_frame.rowconfigure(0, weight=1)
        mosaic_canvas_frame.columnconfigure(0, weight=1)

        h_scroll = ttk.Scrollbar(mosaic_canvas_frame, orient=tk.HORIZONTAL)
        h_scroll.grid(row=1, column=0, sticky="ew")
        v_scroll = ttk.Scrollbar(mosaic_canvas_frame, orient=tk.VERTICAL)
        v_scroll.grid(row=0, column=1, sticky="ns")

        self.auto_mosaic_canvas = tk.Canvas(
            mosaic_canvas_frame, bg=self.colors['canvas'],
            xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set
        )
        self.auto_mosaic_canvas.grid(row=0, column=0, sticky="nsew")
        _style_canvas_widget(self.auto_mosaic_canvas, self.colors['canvas'])
        self.join_free_canvas = self.auto_mosaic_canvas

        h_scroll.config(command=self.auto_mosaic_canvas.xview)
        v_scroll.config(command=self.auto_mosaic_canvas.yview)

        self.auto_mosaic_canvas.bind('<MouseWheel>', self._on_shared_mosaic_mousewheel)
        self.auto_mosaic_canvas.bind('<ButtonPress-2>', self._on_shared_mosaic_pan_start)
        self.auto_mosaic_canvas.bind('<B2-Motion>', self._on_shared_mosaic_pan_drag)
        self.auto_mosaic_canvas.bind('<ButtonPress-3>', self._on_shared_mosaic_pan_start)
        self.auto_mosaic_canvas.bind('<B3-Motion>', self._on_shared_mosaic_pan_drag)

        self.auto_mosaic_info_label = ttk.Label(preview_frame,
                                                 text="Selecciona un grupo o carga imagenes",
                                                 style='Info.TLabel')
        self.auto_mosaic_info_label.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        self.join_free_info_label = self.auto_mosaic_info_label

        main_paned.add(right_panel, stretch='always')
        self._mosaic_source = None
        self._clear_join_free_preview()

    def _setup_auto_join_content(self, parent):
        """Contenido del tab Automatico exportado (sin visor, usa el compartido)."""
        groups_frame = ttk.LabelFrame(parent, text="Grupos detectados", padding=5)
        groups_frame.pack(fill=tk.X, pady=(0, 3))

        groups_table_frame = ttk.Frame(groups_frame)
        groups_table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('grupo', 'carpeta', 'tiles', 'tamano', 'salida')
        self.join_tree = ttk.Treeview(groups_table_frame, columns=columns,
                                       show='headings', height=3)
        self.join_tree.heading('grupo', text='Grupo',
                               command=lambda: self._sort_join_tree_by_column('grupo'))
        self.join_tree.heading('carpeta', text='Carpeta',
                               command=lambda: self._sort_join_tree_by_column('carpeta'))
        self.join_tree.heading('tiles', text='Imgs',
                               command=lambda: self._sort_join_tree_by_column('tiles'))
        self.join_tree.heading('tamano', text='Tamano',
                               command=lambda: self._sort_join_tree_by_column('tamano'))
        self.join_tree.heading('salida', text='Salida',
                               command=lambda: self._sort_join_tree_by_column('salida'))
        self.join_tree.column('grupo', width=140, anchor=tk.W)
        self.join_tree.column('carpeta', width=160, anchor=tk.W)
        self.join_tree.column('tiles', width=45, anchor=tk.CENTER)
        self.join_tree.column('tamano', width=75, anchor=tk.CENTER)
        self.join_tree.column('salida', width=130, anchor=tk.W)
        self.join_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.join_tree.bind('<<TreeviewSelect>>', self._on_auto_group_select)
        self._join_tree_sort_state = {}  # {col: ascending_bool}

        join_scroll = ttk.Scrollbar(groups_table_frame, command=self.join_tree.yview)
        join_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.join_tree.config(yscrollcommand=join_scroll.set)

        group_action_frame = ttk.Frame(groups_frame)
        group_action_frame.pack(fill=tk.X, pady=(3, 0))

        self.btn_join_selected = ttk.Button(group_action_frame, text="Juntar seleccionados",
                                            style='Secondary.TButton',
                                            command=self._start_join_selected, state=tk.DISABLED)
        self.btn_join_selected.pack(side=tk.RIGHT, padx=5)

        self.btn_join_all = ttk.Button(group_action_frame, text="Juntar todos",
                                       style='Action.TButton',
                                       command=self._start_join_all, state=tk.DISABLED)
        self.btn_join_all.pack(side=tk.RIGHT, padx=5)

        tiles_frame = ttk.LabelFrame(parent, text="Imagenes del grupo seleccionado", padding=5)
        tiles_frame.pack(fill=tk.BOTH, expand=True, pady=(3, 3))

        # --- Barra de filtros ---
        filter_frame = ttk.Frame(tiles_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 4))

        # Busqueda por texto
        ttk.Label(filter_frame, text="🔍", font=(UI_FONT_FAMILY, 10)).pack(side=tk.LEFT, padx=(0, 2))
        self.auto_tile_search_var = tk.StringVar()
        self.auto_tile_search_var.trace_add('write', lambda *_: self._apply_auto_tile_filters())
        search_entry = ttk.Entry(filter_frame, textvariable=self.auto_tile_search_var, width=18)
        search_entry.pack(side=tk.LEFT, padx=(0, 6))

        # Filtro por tamano
        ttk.Label(filter_frame, text="Tamaño:", font=(UI_FONT_FAMILY, 9)).pack(side=tk.LEFT, padx=(4, 2))
        self.auto_tile_size_filter_var = tk.StringVar(value='Todos')
        self.auto_tile_size_combo = ttk.Combobox(
            filter_frame, textvariable=self.auto_tile_size_filter_var,
            state='readonly', width=12
        )
        self.auto_tile_size_combo['values'] = ['Todos']
        self.auto_tile_size_combo.pack(side=tk.LEFT, padx=(0, 6))
        self.auto_tile_size_combo.bind('<<ComboboxSelected>>', lambda *_: self._apply_auto_tile_filters())

        # Filtro por carpeta
        ttk.Label(filter_frame, text="Carpeta:", font=(UI_FONT_FAMILY, 9)).pack(side=tk.LEFT, padx=(4, 2))
        self.auto_tile_folder_filter_var = tk.StringVar(value='Todos')
        self.auto_tile_folder_combo = ttk.Combobox(
            filter_frame, textvariable=self.auto_tile_folder_filter_var,
            state='readonly', width=16
        )
        self.auto_tile_folder_combo['values'] = ['Todos']
        self.auto_tile_folder_combo.pack(side=tk.LEFT, padx=(0, 6))
        self.auto_tile_folder_combo.bind('<<ComboboxSelected>>', lambda *_: self._apply_auto_tile_filters())

        # Boton limpiar filtros
        ttk.Button(filter_frame, text="✕ Limpiar", width=9,
                   command=self._clear_auto_tile_filters).pack(side=tk.LEFT, padx=(4, 0))

        self.auto_tile_filter_info = ttk.Label(filter_frame, text="", style='Info.TLabel')
        self.auto_tile_filter_info.pack(side=tk.RIGHT, padx=(6, 0))

        # --- Barra de ordenamiento ---
        sort_frame = ttk.Frame(tiles_frame)
        sort_frame.pack(fill=tk.X, pady=(0, 4))

        ttk.Label(sort_frame, text="Ordenar por:", font=(UI_FONT_FAMILY, 9, 'bold')).pack(side=tk.LEFT, padx=(0, 4))

        self.auto_tile_sort_var = tk.StringVar(value='Original')
        self.auto_tile_sort_combo = ttk.Combobox(
            sort_frame, textvariable=self.auto_tile_sort_var,
            state='readonly', width=16
        )
        self.auto_tile_sort_combo['values'] = [
            'Original',
            'Nombre (natural)',
            'Progresiva',
            'Tramo',
            'Índice + Palabra',
            'Palabra + Índice',
            'Tamaño',
            'Índice'
        ]
        self.auto_tile_sort_combo.pack(side=tk.LEFT, padx=(0, 4))
        self.auto_tile_sort_combo.bind('<<ComboboxSelected>>', lambda *_: self._sort_auto_tiles())

        self.auto_tile_sort_dir_var = tk.StringVar(value='▲ Asc')
        self.auto_tile_sort_dir_btn = ttk.Button(
            sort_frame, textvariable=self.auto_tile_sort_dir_var, width=7,
            command=self._toggle_sort_direction
        )
        self.auto_tile_sort_dir_btn.pack(side=tk.LEFT, padx=(0, 6))

        # Separador visual
        ttk.Separator(sort_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=(2, 6), pady=2)

        # Campo de palabra clave para agrupar
        ttk.Label(sort_frame, text="Palabra:", font=(UI_FONT_FAMILY, 9)).pack(side=tk.LEFT, padx=(0, 2))
        self.auto_tile_sort_keyword_var = tk.StringVar()
        keyword_entry = ttk.Entry(sort_frame, textvariable=self.auto_tile_sort_keyword_var, width=14)
        keyword_entry.pack(side=tk.LEFT, padx=(0, 4))
        # Al presionar Enter en el campo de palabra, ordenar
        keyword_entry.bind('<Return>', lambda *_: self._sort_auto_tiles())

        ttk.Button(sort_frame, text="Agrupar", width=8,
                   command=self._group_by_keyword_and_sort).pack(side=tk.LEFT, padx=(0, 4))

        ttk.Button(sort_frame, text="Auto Columnas", width=13,
                   command=self._arrange_columns_by_keyword).pack(side=tk.LEFT, padx=(0, 4))

        ttk.Button(sort_frame, text="↺ Reset", width=7,
                   command=self._reset_auto_tile_sort).pack(side=tk.LEFT, padx=(4, 0))

        self.auto_tile_sort_info = ttk.Label(sort_frame, text="", style='Info.TLabel')
        self.auto_tile_sort_info.pack(side=tk.RIGHT, padx=(6, 0))

        # --- Tabla de tiles ---
        auto_tiles_table = ttk.Frame(tiles_frame)
        auto_tiles_table.pack(fill=tk.BOTH, expand=True)
        auto_tiles_table.rowconfigure(0, weight=1)
        auto_tiles_table.columnconfigure(0, weight=1)

        auto_tile_cols = ('orden', 'archivo', 'tamano', 'indice')
        self.auto_tiles_tree = ttk.Treeview(
            auto_tiles_table, columns=auto_tile_cols,
            show='headings', selectmode='extended', height=6
        )
        self.auto_tiles_tree.heading('orden', text='#',
                                      command=lambda: self._sort_auto_tiles_by_column('orden'))
        self.auto_tiles_tree.heading('archivo', text='Archivo',
                                     command=lambda: self._sort_auto_tiles_by_column('archivo'))
        self.auto_tiles_tree.heading('tamano', text='Tamano',
                                     command=lambda: self._sort_auto_tiles_by_column('tamano'))
        self.auto_tiles_tree.heading('indice', text='Ind.',
                                     command=lambda: self._sort_auto_tiles_by_column('indice'))
        self.auto_tiles_tree.column('orden', width=30, anchor=tk.CENTER)
        self.auto_tiles_tree.column('archivo', width=170, anchor=tk.W)
        self.auto_tiles_tree.column('tamano', width=70, anchor=tk.CENTER)
        self.auto_tiles_tree.column('indice', width=40, anchor=tk.CENTER)
        self.auto_tiles_tree.grid(row=0, column=0, sticky="nsew")
        self._auto_tiles_col_sort_state = {}  # {col: ascending_bool}

        auto_tiles_scroll = ttk.Scrollbar(auto_tiles_table, command=self.auto_tiles_tree.yview)
        auto_tiles_scroll.grid(row=0, column=1, sticky="ns")
        self.auto_tiles_tree.config(yscrollcommand=auto_tiles_scroll.set)

        auto_order_frame = ttk.Frame(tiles_frame)
        auto_order_frame.pack(fill=tk.X, pady=(4, 0))

        ttk.Button(auto_order_frame, text="Subir",
                   command=lambda: self._move_auto_tile(-1)).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(auto_order_frame, text="Bajar",
                   command=lambda: self._move_auto_tile(1)).pack(side=tk.LEFT, padx=5)

        self.auto_tiles_count_label = ttk.Label(auto_order_frame, text="0 tiles", style='Info.TLabel')
        self.auto_tiles_count_label.pack(side=tk.LEFT, padx=10)

        log_frame = ttk.LabelFrame(parent, text="Registro Join", padding=4)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.join_status_text = tk.Text(log_frame, height=3, wrap=tk.WORD,
                                        font=(UI_MONO_FONT_FAMILY, 9))
        self.join_status_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        _style_text_widget(self.join_status_text)

        join_log_scroll = ttk.Scrollbar(log_frame, command=self.join_status_text.yview)
        join_log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.join_status_text.config(yscrollcommand=join_log_scroll.set)

    def _setup_free_join_content(self, parent):
        """Contenido del tab Visor libre (sin visor propio, usa el compartido)."""
        list_frame = ttk.LabelFrame(parent, text="Imagenes para juntar", padding=8)
        list_frame.pack(fill=tk.BOTH, expand=True)
        list_frame.rowconfigure(1, weight=1)
        list_frame.columnconfigure(0, weight=1)

        toolbar = ttk.Frame(list_frame)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(toolbar, text="Cargar carpeta",
                   command=self._load_join_free_folder).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(toolbar, text="Agregar archivos",
                   command=self._add_join_free_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Quitar",
                   command=self._remove_join_free_selection).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Limpiar",
                   command=self._clear_join_free_images).pack(side=tk.LEFT, padx=5)

        free_table_frame = ttk.Frame(list_frame)
        free_table_frame.grid(row=1, column=0, sticky="nsew")
        free_table_frame.rowconfigure(0, weight=1)
        free_table_frame.columnconfigure(0, weight=1)

        columns = ('orden', 'archivo', 'tamano', 'carpeta')
        self.join_free_tree = ttk.Treeview(
            free_table_frame, columns=columns,
            show='headings', selectmode='extended', height=10
        )
        self.join_free_tree.heading('orden', text='#')
        self.join_free_tree.heading('archivo', text='Archivo')
        self.join_free_tree.heading('tamano', text='Tamano')
        self.join_free_tree.heading('carpeta', text='Carpeta')
        self.join_free_tree.column('orden', width=40, anchor=tk.CENTER)
        self.join_free_tree.column('archivo', width=180, anchor=tk.W)
        self.join_free_tree.column('tamano', width=80, anchor=tk.CENTER)
        self.join_free_tree.column('carpeta', width=200, anchor=tk.W)
        self.join_free_tree.grid(row=0, column=0, sticky="nsew")
        self.join_free_tree.bind('<<TreeviewSelect>>', self._on_join_free_select)

        free_scroll = ttk.Scrollbar(free_table_frame, command=self.join_free_tree.yview)
        free_scroll.grid(row=0, column=1, sticky="ns")
        self.join_free_tree.config(yscrollcommand=free_scroll.set)

        order_frame = ttk.Frame(list_frame)
        order_frame.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(order_frame, text="Subir",
                   command=lambda: self._move_join_free_selection(-1)).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(order_frame, text="Bajar",
                   command=lambda: self._move_join_free_selection(1)).pack(side=tk.LEFT, padx=5)

        self.btn_join_free_selected = ttk.Button(
            order_frame, text="Juntar seleccionadas",
            style='Secondary.TButton', command=self._start_join_free_selected, state=tk.DISABLED
        )
        self.btn_join_free_selected.pack(side=tk.RIGHT, padx=5)

        self.btn_join_free_all = ttk.Button(
            order_frame, text="Juntar visor",
            style='Action.TButton', command=self._start_join_free_all, state=tk.DISABLED
        )
        self.btn_join_free_all.pack(side=tk.RIGHT, padx=5)

    # ==================== Shared mosaic methods ====================

    def _zoom_shared_mosaic(self, factor):
        """Zoom compartido: opera sobre el mosaico activo (auto o libre)."""
        if self._mosaic_source == 'auto':
            self._zoom_auto_mosaic(factor)
        elif self._mosaic_source == 'libre':
            self._zoom_mosaic_preview(factor)

    def _reset_shared_mosaic_zoom(self):
        """Reset zoom compartido."""
        if self._mosaic_source == 'auto':
            self._reset_auto_mosaic_zoom()
        elif self._mosaic_source == 'libre':
            self._reset_mosaic_zoom()

    def _on_shared_mosaic_mousewheel(self, event):
        """Mousewheel en canvas compartido."""
        if event.delta > 0:
            self._zoom_shared_mosaic(1.15)
        else:
            self._zoom_shared_mosaic(0.85)

    def _on_shared_mosaic_pan_start(self, event):
        """Pan start en canvas compartido."""
        self.auto_mosaic_drag_x = event.x
        self.auto_mosaic_drag_y = event.y

    def _on_shared_mosaic_pan_drag(self, event):
        """Pan drag en canvas compartido."""
        dx = event.x - self.auto_mosaic_drag_x
        dy = event.y - self.auto_mosaic_drag_y
        self.auto_mosaic_canvas.xview_scroll(-int(dx), "units")
        self.auto_mosaic_canvas.yview_scroll(-int(dy), "units")
        self.auto_mosaic_drag_x = event.x
        self.auto_mosaic_drag_y = event.y

    def _save_current_mosaic_result(self):
        """Guarda el mosaico activo (auto o libre)."""
        if self._mosaic_source == 'auto':
            self._save_auto_mosaic_result()
        elif self._mosaic_source == 'libre':
            self._save_mosaic_result()
        else:
            messagebox.showinfo("Info", "Genera una vista previa primero")

    def _join_image_filetypes(self):
        return (
            ("Imagenes", "*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.webp"),
            ("Todos los archivos", "*.*")
        )

    def _load_join_free_folder(self):
        input_dir = self._get_join_input_dir()
        if not input_dir:
            directory = filedialog.askdirectory(title="Seleccionar carpeta de imagenes", initialdir=os.getcwd())
            if not directory:
                return
            input_dir = directory
            self.join_input_dir.set(directory)

        if not os.path.isdir(input_dir):
            messagebox.showwarning("Advertencia", f"La carpeta no existe:\n{input_dir}")
            return

        records = RoadImageProcessor.scan_image_files(
            input_dir,
            self.join_include_subfolders.get()
        )
        self.join_free_images = records
        if not self.join_output_dir.get().strip():
            self.join_output_dir.set(os.path.join(input_dir, "joined"))

        self._refresh_join_free_tree()
        self._log_join(f"Visor libre: {len(records)} imagenes cargadas desde {input_dir}")
        if not records:
            messagebox.showinfo("Sin imagenes", "No se encontraron imagenes compatibles en la carpeta")

    def _add_join_free_files(self):
        initial = self._get_join_input_dir() or os.getcwd()
        file_paths = filedialog.askopenfilenames(
            title="Agregar imagenes al visor",
            initialdir=initial,
            filetypes=self._join_image_filetypes()
        )
        if not file_paths:
            return

        existing = {item['path'].lower() for item in self.join_free_images}
        added = 0
        for file_path in file_paths:
            record = RoadImageProcessor._image_record(file_path)
            if record and record['path'].lower() not in existing:
                self.join_free_images.append(record)
                existing.add(record['path'].lower())
                added += 1

        if not self.join_output_dir.get().strip() and self.join_free_images:
            self.join_output_dir.set(os.path.join(os.path.dirname(self.join_free_images[0]['path']), "joined"))

        self._refresh_join_free_tree()
        self._log_join(f"Visor libre: {added} imagenes agregadas")

    def _refresh_join_free_tree(self, selected_indices=None):
        for item in self.join_free_tree.get_children():
            self.join_free_tree.delete(item)

        for idx, record in enumerate(self.join_free_images):
            self.join_free_tree.insert(
                '',
                tk.END,
                iid=str(idx),
                values=(idx, record['name'], record['size'], record['folder'])
            )

        self._set_join_free_buttons_state()

        # Invalidar el mosaico cuando cambia la lista de imagenes
        if self.join_mosaic_pil is not None:
            self.join_free_info_label.config(
                text="La lista cambio. Genera la vista previa de nuevo."
            )
            if hasattr(self, 'btn_save_mosaic'):
                self.btn_save_mosaic.config(state=tk.DISABLED)

        if selected_indices:
            valid = [str(idx) for idx in selected_indices if 0 <= idx < len(self.join_free_images)]
            if valid:
                self.join_free_tree.selection_set(valid)
                self.join_free_tree.focus(valid[0])
                self.join_free_tree.see(valid[0])
                return

        if self.join_free_images:
            self.join_free_tree.selection_set("0")
            self.join_free_tree.focus("0")
        else:
            self._clear_join_free_preview()

    def _set_join_free_buttons_state(self):
        if not hasattr(self, 'btn_join_free_all'):
            return

        has_images = bool(self.join_free_images)
        state = tk.NORMAL if has_images and not self.join_processing else tk.DISABLED
        self.btn_join_free_all.config(state=state)
        self.btn_join_free_selected.config(state=state)
        if hasattr(self, 'btn_generate_mosaic'):
            self.btn_generate_mosaic.config(state=state)

    def _on_join_free_select(self, event=None):
        """Al seleccionar una imagen de la lista, no cambiamos el mosaico,
        pero mantenemos el estado de los botones actualizado."""
        pass

    def _render_join_free_selected_preview(self):
        """No se usa para preview individual; ahora el canvas muestra el mosaico."""
        pass

    def _render_join_free_preview(self, record):
        """Compatibilidad: ya no muestra preview individual."""
        pass

    def _clear_join_free_preview(self, message="Carga imagenes y genera la vista previa del mosaico"):
        if not hasattr(self, 'join_free_canvas'):
            return

        self.join_mosaic_pil = None
        self.join_mosaic_photo = None
        self.join_mosaic_zoom = 1.0
        if hasattr(self, 'btn_save_mosaic'):
            self.btn_save_mosaic.config(state=tk.DISABLED)

        self.join_free_canvas.delete("all")
        self.join_free_canvas.update_idletasks()
        canvas_w = max(240, self.join_free_canvas.winfo_width())
        canvas_h = max(220, self.join_free_canvas.winfo_height())
        self.join_free_canvas.config(scrollregion=(0, 0, canvas_w, canvas_h))
        self.join_free_canvas.create_rectangle(0, 0, canvas_w, canvas_h, fill=self.colors['canvas'], outline="")
        self.join_free_canvas.create_text(
            canvas_w // 2,
            canvas_h // 2,
            text=message,
            fill=self.colors['canvas_text'],
            font=(UI_FONT_FAMILY, 11, 'bold')
        )
        self.join_free_info_label.config(text=message)

    # ==================== Mosaic preview methods ====================

    def _generate_mosaic_preview(self):
        """Genera el mosaico completo en memoria y lo muestra en el canvas."""
        if not self.join_free_images:
            messagebox.showinfo("Info", "Carga imagenes primero")
            return

        columns = max(0, self.join_columns.get())
        spacing = max(0, self.join_spacing.get())
        paths = [record['path'] for record in self.join_free_images]

        if columns <= 0:
            columns = 1  # Vertical por defecto (pavimento)
        else:
            columns = min(columns, len(paths))
        rows = math.ceil(len(paths) / columns)

        self.join_free_info_label.config(text="Generando mosaico...")
        self.root.update_idletasks()

        try:
            # Leer tamaños de todas las imagenes
            sizes = []
            for path in paths:
                with Image.open(path) as img:
                    sizes.append(img.size)

            cell_w = max(w for w, _ in sizes)
            cell_h = max(h for _, h in sizes)
            joined_w = columns * cell_w + spacing * (columns - 1)
            joined_h = rows * cell_h + spacing * (rows - 1)

            # Limitar la resolución del mosaico en memoria para evitar OOM
            MAX_PIXELS = 200_000_000  # ~200 MP max
            total_px = joined_w * joined_h
            if total_px > MAX_PIXELS:
                scale_down = math.sqrt(MAX_PIXELS / total_px)
                joined_w = int(joined_w * scale_down)
                joined_h = int(joined_h * scale_down)
                cell_w = int(cell_w * scale_down)
                cell_h = int(cell_h * scale_down)
                spacing = int(spacing * scale_down)

            canvas_img = Image.new("RGB", (joined_w, joined_h), (255, 255, 255))

            for idx, path in enumerate(paths):
                row = idx // columns
                col = idx % columns
                x = col * (cell_w + spacing)
                y = row * (cell_h + spacing)

                with Image.open(path) as img:
                    tile = img.convert("RGB")
                    # Redimensionar el tile si es necesario
                    if tile.size != (cell_w, cell_h):
                        tile = tile.resize((cell_w, cell_h), Image.LANCZOS)
                    canvas_img.paste(tile, (x, y))

            self.join_mosaic_pil = canvas_img
            self.join_mosaic_zoom = 1.0

            # Mostrar ajustado al canvas
            self._fit_mosaic_to_canvas()
            self.btn_save_mosaic.config(state=tk.NORMAL)

            info = f"Mosaico: {joined_w}x{joined_h}px | {columns} columnas x {rows} filas | {len(paths)} imagenes"
            self.join_free_info_label.config(text=info)
            self._log_join(f"Vista previa generada: {info}")

        except Exception as e:
            self._clear_join_free_preview(f"Error generando mosaico: {e}")
            import traceback
            self._log_join(f"Error generando mosaico:\n{traceback.format_exc()}")

    def _fit_mosaic_to_canvas(self):
        """Ajusta el zoom para que el mosaico quepa en el canvas visible."""
        if self.join_mosaic_pil is None:
            return

        self.join_free_canvas.update_idletasks()
        canvas_w = max(240, self.join_free_canvas.winfo_width())
        canvas_h = max(220, self.join_free_canvas.winfo_height())

        img_w, img_h = self.join_mosaic_pil.size
        scale_x = (canvas_w - 20) / img_w if img_w > 0 else 1.0
        scale_y = (canvas_h - 20) / img_h if img_h > 0 else 1.0
        self.join_mosaic_zoom = min(scale_x, scale_y, 1.0)

        self._render_mosaic_at_zoom()

    def _render_mosaic_at_zoom(self):
        """Renderiza el mosaico PIL en el canvas al nivel de zoom actual."""
        if self.join_mosaic_pil is None:
            return

        img_w, img_h = self.join_mosaic_pil.size
        display_w = max(1, int(img_w * self.join_mosaic_zoom))
        display_h = max(1, int(img_h * self.join_mosaic_zoom))

        resized = self.join_mosaic_pil.resize(
            (display_w, display_h),
            Image.LANCZOS if self.join_mosaic_zoom < 1.0 else Image.NEAREST
        )

        self.join_mosaic_photo = ImageTk.PhotoImage(resized)
        self.join_free_canvas.delete("all")
        self.join_free_canvas.create_image(0, 0, anchor=tk.NW, image=self.join_mosaic_photo)
        self.join_free_canvas.config(scrollregion=(0, 0, display_w, display_h))

        self.mosaic_zoom_label.config(text=f"{int(self.join_mosaic_zoom * 100)}%")

    def _zoom_mosaic_preview(self, factor):
        """Aplica zoom al mosaico preview."""
        if self.join_mosaic_pil is None:
            return
        new_zoom = self.join_mosaic_zoom * factor
        new_zoom = max(0.02, min(5.0, new_zoom))
        self.join_mosaic_zoom = new_zoom
        self._render_mosaic_at_zoom()

    def _reset_mosaic_zoom(self):
        """Resetea el zoom del mosaico para ajustarlo al canvas."""
        if self.join_mosaic_pil is None:
            return
        self._fit_mosaic_to_canvas()

    def _on_mosaic_mousewheel(self, event):
        """Zoom con rueda del raton en el canvas del mosaico."""
        if self.join_mosaic_pil is None:
            return
        if event.delta > 0:
            self._zoom_mosaic_preview(1.15)
        else:
            self._zoom_mosaic_preview(0.85)

    def _on_mosaic_pan_start(self, event):
        """Inicia el arrastre para pan del mosaico."""
        self.join_mosaic_drag_x = event.x
        self.join_mosaic_drag_y = event.y

    def _on_mosaic_pan_drag(self, event):
        """Pan del mosaico arrastrando con boton central/derecho."""
        dx = event.x - self.join_mosaic_drag_x
        dy = event.y - self.join_mosaic_drag_y
        self.join_free_canvas.xview_scroll(-int(dx), "units")
        self.join_free_canvas.yview_scroll(-int(dy), "units")
        self.join_mosaic_drag_x = event.x
        self.join_mosaic_drag_y = event.y

    def _save_mosaic_result(self):
        """Guarda el mosaico generado en la vista previa."""
        if self.join_mosaic_pil is None:
            messagebox.showinfo("Info", "Genera la vista previa del mosaico primero")
            return

        output_dir = self._get_join_output_dir()
        os.makedirs(output_dir, exist_ok=True)

        # Generar nombre
        base_dir = self._get_join_input_dir()
        base_name = os.path.basename(base_dir.rstrip("\\/")) if base_dir else "join_libre"
        safe_name = RoadImageProcessor._safe_filename(base_name)
        output_name = f"{safe_name}_join.png"
        output_path = os.path.join(output_dir, output_name)

        # Verificar si el archivo ya existe
        if os.path.exists(output_path):
            counter = 1
            while os.path.exists(output_path):
                output_name = f"{safe_name}_join_{counter:03d}.png"
                output_path = os.path.join(output_dir, output_name)
                counter += 1

        # Reconstruir a tamaño completo (sin scale_down de la preview) para guardar
        columns = max(0, self.join_columns.get())
        spacing = max(0, self.join_spacing.get())
        paths = [record['path'] for record in self.join_free_images]

        if columns <= 0:
            columns = 1  # Vertical por defecto
        else:
            columns = min(columns, len(paths))

        group = self._join_free_group_from_records(self.join_free_images, safe_name)
        if group:
            group['output_name'] = output_name
            try:
                self.join_free_info_label.config(text="Guardando imagen final...")
                self.root.update_idletasks()

                saved_path = RoadImageProcessor.join_tile_group(
                    group,
                    output_dir,
                    columns,
                    spacing,
                    progress_callback=self._log_join
                )
                self._log_join(f"Guardado exitosamente: {saved_path}")
                self.join_free_info_label.config(text=f"Guardado: {saved_path}")
                messagebox.showinfo(
                    "Guardado exitosamente",
                    f"Imagen guardada en:\n{saved_path}"
                )
            except Exception as e:
                self._log_join(f"Error al guardar: {e}")
                messagebox.showerror("Error", f"No se pudo guardar:\n{e}")

    def _remove_join_free_selection(self):
        selected = sorted((int(item) for item in self.join_free_tree.selection()), reverse=True)
        if not selected:
            return

        for idx in selected:
            if 0 <= idx < len(self.join_free_images):
                self.join_free_images.pop(idx)

        next_idx = min(selected[-1], len(self.join_free_images) - 1) if self.join_free_images else None
        self._refresh_join_free_tree([next_idx] if next_idx is not None else None)

    def _clear_join_free_images(self):
        self.join_free_images = []
        self._refresh_join_free_tree()
        self._log_join("Visor libre limpiado")

    def _move_join_free_selection(self, direction):
        selected = sorted(int(item) for item in self.join_free_tree.selection())
        if not selected or not self.join_free_images:
            return

        if direction < 0 and selected[0] == 0:
            return
        if direction > 0 and selected[-1] == len(self.join_free_images) - 1:
            return

        selected_set = set(selected)
        moving = [self.join_free_images[idx] for idx in selected]
        remaining = [record for idx, record in enumerate(self.join_free_images) if idx not in selected_set]

        insert_pos = selected[0] - 1 if direction < 0 else selected[0] + 1
        self.join_free_images = remaining[:insert_pos] + moving + remaining[insert_pos:]
        new_indices = list(range(insert_pos, insert_pos + len(moving)))
        self._refresh_join_free_tree(new_indices)

    def _join_free_group_from_records(self, records, name):
        paths = [record['path'] for record in records]
        if not paths:
            return None

        sizes = sorted({record['size'] for record in records})
        if len(sizes) == 1:
            size_text = sizes[0]
        else:
            size_text = f"variable ({len(sizes)} tamanos)"

        safe_name = RoadImageProcessor._safe_filename(name)
        return {
            'display_name': name,
            'folder': os.path.dirname(paths[0]),
            'prefix': safe_name,
            'tile_count': len(paths),
            'tile_size': size_text,
            'tile_items': list(enumerate(paths)),
            'tile_indices': list(range(len(paths))),
            'paths': paths,
            'output_name': f"{safe_name}_join.png"
        }

    def _start_join_free_all(self):
        if not self.join_free_images:
            messagebox.showinfo("Info", "Carga imagenes en el visor primero")
            return

        base_dir = self._get_join_input_dir()
        base_name = os.path.basename(base_dir.rstrip("\\/")) if base_dir else "join_libre"
        group = self._join_free_group_from_records(self.join_free_images, f"{base_name}_libre")
        if group:
            self._start_join([group])

    def _start_join_free_selected(self):
        selected = sorted(int(item) for item in self.join_free_tree.selection())
        records = [self.join_free_images[idx] for idx in selected if 0 <= idx < len(self.join_free_images)]
        if not records:
            messagebox.showinfo("Info", "Selecciona una o mas imagenes del visor")
            return

        group = self._join_free_group_from_records(records, "join_libre_seleccion")
        if group:
            self._start_join([group])

    def _get_join_input_dir(self):
        input_dir = self.join_input_dir.get().strip()
        if not input_dir and self.output_dir.get().strip():
            input_dir = self.output_dir.get().strip()
            self.join_input_dir.set(input_dir)
        return input_dir

    def _get_join_output_dir(self):
        output_dir = self.join_output_dir.get().strip()
        if not output_dir:
            base_dir = self._get_join_input_dir() or self.output_dir.get().strip() or os.getcwd()
            output_dir = os.path.join(base_dir, "joined")
            self.join_output_dir.set(output_dir)
        return output_dir

    def _select_join_input_dir(self):
        initial = self._get_join_input_dir() or self.output_dir.get().strip() or os.getcwd()
        directory = filedialog.askdirectory(title="Seleccionar carpeta de recortes", initialdir=initial)
        if directory:
            self.join_input_dir.set(directory)
            if not self.join_output_dir.get().strip():
                self.join_output_dir.set(os.path.join(directory, "joined"))

    def _select_join_output_dir(self):
        initial = self._get_join_output_dir() or os.getcwd()
        directory = filedialog.askdirectory(title="Seleccionar carpeta de salida", initialdir=initial)
        if directory:
            self.join_output_dir.set(directory)

    def _use_pci_tramo_grouping(self):
        self.join_group_keyword.set("Progresiva")
        self.join_columns.set(0)
        self.join_start_index.set(0)
        self.join_end_index.set(-1)
        if hasattr(self, 'join_status_text'):
            self._log_join("Modo PCI/TRAMO: agrupa por Progresiva y detecta nomenclaturas como columnas")

    def _scan_join_groups(self):
        input_dir = self._get_join_input_dir()
        if not input_dir:
            messagebox.showwarning("Advertencia", "Selecciona la carpeta donde estan los recortes")
            return
        if not os.path.isdir(input_dir):
            messagebox.showwarning("Advertencia", f"La carpeta no existe:\n{input_dir}")
            return

        self.join_status_text.delete(1.0, tk.END)
        self._log_join(f"Analizando: {input_dir}")
        group_keyword = self.join_group_keyword.get().strip()
        if group_keyword:
            self._log_join(f"Agrupando por palabra: {group_keyword}")

        groups = RoadImageProcessor.scan_tile_groups(
            input_dir,
            self.join_include_subfolders.get(),
            group_keyword
        )
        self.join_groups = groups

        self._refresh_join_groups_tree()

        self._set_join_buttons_state(bool(groups))
        if groups:
            total_tiles = sum(group['tile_count'] for group in groups)
            self._log_join(f"Grupos detectados: {len(groups)} | Imagenes: {total_tiles}")
            self._get_join_output_dir()
        else:
            self._log_join("No se encontraron imagenes compatibles con la agrupacion indicada")
            messagebox.showinfo("Sin grupos", "No se encontraron imagenes para juntar con esa agrupacion")

    def _refresh_join_groups_tree(self):
        """Refresca la tabla de grupos detectados con los datos de self.join_groups."""
        for item in self.join_tree.get_children():
            self.join_tree.delete(item)

        for idx, group in enumerate(self.join_groups):
            self.join_tree.insert('', tk.END, iid=str(idx),
                                  values=(group['display_name'],
                                          group['folder'],
                                          group['tile_count'],
                                          group['tile_size'],
                                          group['output_name']))

    def _set_join_buttons_state(self, enabled):
        state = tk.NORMAL if enabled and not self.join_processing else tk.DISABLED
        self.btn_join_all.config(state=state)
        self.btn_join_selected.config(state=state)
        self._set_join_free_buttons_state()

    # ==================== Auto-export mosaic viewer methods ====================

    def _on_auto_group_select(self, event=None):
        """Al seleccionar un grupo en la tabla, cargar sus tiles en la lista de tiles."""
        selected = self.join_tree.selection()
        if not selected:
            return

        try:
            idx = int(selected[0])
            group = self.join_groups[idx]
        except (ValueError, IndexError):
            return

        self.auto_selected_group_idx = idx

        # Auto-configurar columnas desde metadata del grid
        grid_cols = group.get('grid_columns', 0)
        if grid_cols > 0:
            self.join_columns.set(grid_cols)
            self._log_join(f"Columnas auto-detectadas: {grid_cols} (desde metadata)")
        elif self.join_columns.get() == 0:
            # Si no hay metadata y esta en auto, poner 1 (vertical)
            self.join_columns.set(1)
            self._log_join("Sin metadata de grid. Columnas = 1 (vertical)")

        self._load_auto_tiles_from_group(group)

    def _load_auto_tiles_from_group(self, group):
        """Carga los tiles de un grupo en la lista de tiles del visor auto."""
        self.auto_tile_records = []
        self.auto_tile_records_full = []
        tile_items = group.get('tile_items', [])
        paths = group.get('paths', [])

        if tile_items:
            sorted_items = sorted(
                tile_items,
                key=lambda x: (x[0], "" if x[1] is None else str(x[1]).lower())
            )
            for orig_index, path in sorted_items:
                if path:
                    p = Path(path)
                    size_str = ""
                    try:
                        with Image.open(path) as img:
                            size_str = f"{img.size[0]}x{img.size[1]}"
                    except Exception:
                        size_str = "N/D"

                    self.auto_tile_records.append({
                        'path': str(p),
                        'name': p.name,
                        'folder': str(p.parent),
                        'size': size_str,
                        'index': orig_index
                    })
                else:
                    self.auto_tile_records.append({
                        'path': None,
                        'name': "(vacio)",
                        'folder': "",
                        'size': "-",
                        'index': orig_index
                    })
        elif paths:
            for i, path in enumerate(paths):
                p = Path(path)
                size_str = ""
                try:
                    with Image.open(path) as img:
                        size_str = f"{img.size[0]}x{img.size[1]}"
                except Exception:
                    size_str = "N/D"

                self.auto_tile_records.append({
                    'path': str(p),
                    'name': p.name,
                    'folder': str(p.parent),
                    'size': size_str,
                    'index': i
                })

        # Guardar copia completa antes de filtrar
        self.auto_tile_records_full = list(self.auto_tile_records)
        self._update_auto_tile_filter_options()
        self._apply_auto_tile_filters()
        self.auto_mosaic_info_label.config(
            text=f"Grupo: {group.get('display_name', '')} | {len(self.auto_tile_records_full)} tiles cargados"
        )
        self._log_join(f"Tiles cargados del grupo '{group.get('display_name', '')}': {len(self.auto_tile_records_full)}")

        # Limpiar mosaico previo
        self.auto_mosaic_pil = None
        self.auto_mosaic_photo = None
        self.auto_mosaic_zoom = 1.0
        if hasattr(self, 'auto_mosaic_canvas'):
            self.auto_mosaic_canvas.delete("all")
            self.auto_mosaic_canvas.update_idletasks()
            cw = max(240, self.auto_mosaic_canvas.winfo_width())
            ch = max(220, self.auto_mosaic_canvas.winfo_height())
            self.auto_mosaic_canvas.config(scrollregion=(0, 0, cw, ch))
            self.auto_mosaic_canvas.create_text(
                cw // 2, ch // 2,
                text="Haz click en 'Generar vista previa'\npara ver el mosaico",
                fill=self.colors['canvas_text'],
                font=(UI_FONT_FAMILY, 11, 'bold'),
                justify=tk.CENTER
            )
        if hasattr(self, 'btn_auto_save_mosaic'):
            self.btn_auto_save_mosaic.config(state=tk.DISABLED)

    def _refresh_auto_tiles_tree(self, selected_indices=None):
        """Refresca la tabla de tiles del visor auto."""
        for item in self.auto_tiles_tree.get_children():
            self.auto_tiles_tree.delete(item)

        for idx, rec in enumerate(self.auto_tile_records):
            self.auto_tiles_tree.insert(
                '', tk.END, iid=str(idx),
                values=(idx, rec['name'], rec['size'], rec['index'])
            )

        count = len(self.auto_tile_records)
        total = len(self.auto_tile_records_full) if self.auto_tile_records_full else count
        if count < total:
            self.auto_tiles_count_label.config(text=f"{count}/{total} tiles")
        else:
            self.auto_tiles_count_label.config(text=f"{count} tiles")

        # Habilitar/deshabilitar boton generar
        if hasattr(self, 'btn_auto_generate_mosaic'):
            state = tk.NORMAL if count > 0 and not self.join_processing else tk.DISABLED
            self.btn_auto_generate_mosaic.config(state=state)

        # Invalidar mosaico si la lista cambio
        if self.auto_mosaic_pil is not None:
            self.auto_mosaic_info_label.config(text="El orden cambio. Genera la vista previa de nuevo.")
            if hasattr(self, 'btn_auto_save_mosaic'):
                self.btn_auto_save_mosaic.config(state=tk.DISABLED)

        if selected_indices:
            valid = [str(i) for i in selected_indices if 0 <= i < count]
            if valid:
                self.auto_tiles_tree.selection_set(valid)
                self.auto_tiles_tree.focus(valid[0])
                self.auto_tiles_tree.see(valid[0])
                return

        if self.auto_tile_records:
            self.auto_tiles_tree.selection_set("0")
            self.auto_tiles_tree.focus("0")

    def _update_auto_tile_filter_options(self):
        """Actualiza las opciones de los combos de filtro según los datos cargados."""
        sizes = set()
        folders = set()
        for rec in self.auto_tile_records_full:
            if rec.get('size') and rec['size'] not in ('-', 'N/D', ''):
                sizes.add(rec['size'])
            folder = rec.get('folder', '')
            if folder:
                # Usar solo el nombre de la ultima carpeta para legibilidad
                folder_short = os.path.basename(folder) if folder else ''
                if folder_short:
                    folders.add(folder_short)

        size_list = ['Todos'] + sorted(sizes)
        folder_list = ['Todos'] + sorted(folders)

        if hasattr(self, 'auto_tile_size_combo'):
            self.auto_tile_size_combo['values'] = size_list
            self.auto_tile_size_filter_var.set('Todos')
        if hasattr(self, 'auto_tile_folder_combo'):
            self.auto_tile_folder_combo['values'] = folder_list
            self.auto_tile_folder_filter_var.set('Todos')
        if hasattr(self, 'auto_tile_search_var'):
            self.auto_tile_search_var.set('')

    def _apply_auto_tile_filters(self, *args):
        """Aplica los filtros de texto, tamaño y carpeta sobre la lista completa."""
        if not self.auto_tile_records_full:
            self.auto_tile_records = []
            self._refresh_auto_tiles_tree()
            return

        search_text = ''
        size_filter = 'Todos'
        folder_filter = 'Todos'

        if hasattr(self, 'auto_tile_search_var'):
            search_text = self.auto_tile_search_var.get().strip().lower()
        if hasattr(self, 'auto_tile_size_filter_var'):
            size_filter = self.auto_tile_size_filter_var.get()
        if hasattr(self, 'auto_tile_folder_filter_var'):
            folder_filter = self.auto_tile_folder_filter_var.get()

        filtered = []
        for rec in self.auto_tile_records_full:
            # Filtro por texto (busca en nombre de archivo)
            if search_text:
                name_lower = rec.get('name', '').lower()
                if search_text not in name_lower:
                    continue

            # Filtro por tamaño
            if size_filter != 'Todos':
                if rec.get('size', '') != size_filter:
                    continue

            # Filtro por carpeta
            if folder_filter != 'Todos':
                folder_short = os.path.basename(rec.get('folder', '')) if rec.get('folder') else ''
                if folder_short != folder_filter:
                    continue

            filtered.append(rec)

        self.auto_tile_records = filtered
        self._refresh_auto_tiles_tree()

        # Actualizar info de filtro
        total = len(self.auto_tile_records_full)
        shown = len(filtered)
        if hasattr(self, 'auto_tile_filter_info'):
            if shown < total:
                self.auto_tile_filter_info.config(text=f"Mostrando {shown} de {total}")
            else:
                self.auto_tile_filter_info.config(text="")

    def _clear_auto_tile_filters(self):
        """Limpia todos los filtros y muestra todos los tiles."""
        if hasattr(self, 'auto_tile_search_var'):
            self.auto_tile_search_var.set('')
        if hasattr(self, 'auto_tile_size_filter_var'):
            self.auto_tile_size_filter_var.set('Todos')
        if hasattr(self, 'auto_tile_folder_filter_var'):
            self.auto_tile_folder_filter_var.set('Todos')
        self._apply_auto_tile_filters()

    # ---------- Métodos de ordenamiento ----------

    @staticmethod
    def _extract_progresiva(name: str) -> str:
        """Extrae la parte de Progresiva del nombre para usarla como clave de orden.
        Ejemplo: PCI_TRAMO_02_01_Progresiva_01+120_01+140 -> 'Progresiva_01+120_01+140'
        """
        match = re.search(r'(?i)(Progresiva[_\s-]*[\d+]+[_\s-]*[\d+]*)', name)
        if match:
            return match.group(1).strip('_ ')
        return name

    @staticmethod
    def _extract_tramo(name: str) -> str:
        """Extrae la parte de TRAMO del nombre para usarla como clave de orden.
        Ejemplo: PCI_TRAMO_02_01_Progresiva_01+120_01+140 -> 'TRAMO_02_01'
        """
        match = re.search(r'(?i)(TRAMO[_\s-]*\d+[_\s-]*\d*)', name)
        if match:
            return match.group(1).strip('_ ')
        return name

    def _sort_auto_tiles(self):
        """Ordena la lista completa de tiles según el criterio seleccionado."""
        criteria = self.auto_tile_sort_var.get() if hasattr(self, 'auto_tile_sort_var') else 'Original'
        ascending = self.auto_tile_sort_ascending

        if not self.auto_tile_records_full:
            return

        nat_key = RoadImageProcessor._natural_sort_key

        if criteria == 'Nombre (natural)':
            self.auto_tile_records_full.sort(
                key=lambda rec: nat_key(rec.get('name', '')),
                reverse=not ascending
            )
            sort_desc = 'nombre'
        elif criteria == 'Progresiva':
            self.auto_tile_records_full.sort(
                key=lambda rec: (
                    nat_key(self._extract_progresiva(rec.get('name', ''))),
                    nat_key(rec.get('name', ''))
                ),
                reverse=not ascending
            )
            sort_desc = 'progresiva'
        elif criteria == 'Tramo':
            self.auto_tile_records_full.sort(
                key=lambda rec: (
                    nat_key(self._extract_tramo(rec.get('name', ''))),
                    nat_key(rec.get('name', ''))
                ),
                reverse=not ascending
            )
            sort_desc = 'tramo'
        elif criteria == 'Índice + Palabra':
            keyword = self.auto_tile_sort_keyword_var.get().strip() if hasattr(self, 'auto_tile_sort_keyword_var') else ''
            self.auto_tile_records_full.sort(
                key=lambda rec: (
                    rec.get('index', 0),
                    nat_key(self._extract_keyword_group(rec.get('name', ''), keyword))
                ),
                reverse=not ascending
            )
            sort_desc = f'índice + "{keyword}"' if keyword else 'índice'
        elif criteria == 'Palabra + Índice':
            keyword = self.auto_tile_sort_keyword_var.get().strip() if hasattr(self, 'auto_tile_sort_keyword_var') else ''
            self.auto_tile_records_full.sort(
                key=lambda rec: (
                    nat_key(self._extract_keyword_group(rec.get('name', ''), keyword)),
                    rec.get('index', 0)
                ),
                reverse=not ascending
            )
            sort_desc = f'"{keyword}" + índice' if keyword else 'nombre'
        elif criteria == 'Tamaño':
            self.auto_tile_records_full.sort(
                key=lambda rec: nat_key(rec.get('size', '')),
                reverse=not ascending
            )
            sort_desc = 'tamaño'
        elif criteria == 'Índice':
            self.auto_tile_records_full.sort(
                key=lambda rec: rec.get('index', 0),
                reverse=not ascending
            )
            sort_desc = 'índice'
        else:
            # 'Original' — restaurar orden por índice original
            self.auto_tile_records_full.sort(key=lambda rec: rec.get('index', 0))
            sort_desc = 'original'

        direction = '▲' if ascending else '▼'
        if hasattr(self, 'auto_tile_sort_info'):
            self.auto_tile_sort_info.config(text=f"Ordenado por {sort_desc} {direction}")

        self._apply_auto_tile_filters()

    def _toggle_sort_direction(self):
        """Alterna entre orden ascendente y descendente y re-ordena."""
        self.auto_tile_sort_ascending = not self.auto_tile_sort_ascending
        if self.auto_tile_sort_ascending:
            self.auto_tile_sort_dir_var.set('▲ Asc')
        else:
            self.auto_tile_sort_dir_var.set('▼ Desc')
        self._sort_auto_tiles()

    def _group_by_keyword_and_sort(self):
        """Atajo: selecciona 'Palabra + Índice' y ordena."""
        keyword = self.auto_tile_sort_keyword_var.get().strip() if hasattr(self, 'auto_tile_sort_keyword_var') else ''
        if not keyword:
            messagebox.showinfo("Info", "Escribe una palabra clave en el campo 'Palabra' para agrupar.\n\n"
                                "Ejemplo: Progresiva, TRAMO, CARRIL, PCI, etc.")
            return
        if hasattr(self, 'auto_tile_sort_var'):
            self.auto_tile_sort_var.set('Palabra + Índice')
        self._sort_auto_tiles()

    @staticmethod
    def _extract_keyword_group(name: str, keyword: str) -> str:
        """Extrae la porción del nombre que contiene la palabra clave y su valor.
        Ejemplo: name='PCI_TRAMO_02_01_Progresiva_01+120_01+140', keyword='Progresiva'
                 -> 'Progresiva_01+120_01+140'
        Si keyword='TRAMO' -> 'TRAMO_02_01'
        Busca la palabra y toma todo desde ella hasta el siguiente segmento reconocible o el final.
        """
        if not keyword:
            return name
        # Buscar la palabra clave en el nombre (case-insensitive)
        match = re.search(re.escape(keyword), name, flags=re.IGNORECASE)
        if not match:
            return '\xff' + name  # Los que no contienen la palabra van al final
        # Tomar desde la palabra hasta el final del nombre (sin extensión)
        base = os.path.splitext(name)[0] if '.' in name else name
        extracted = base[match.start():].strip('_ -')
        return extracted if extracted else name

    @staticmethod
    def _extract_keyword_variant(name: str, keyword: str) -> str:
        """Extrae la palabra clave y sus identificadores cortos (ej: TRAMO_02_01)."""
        if not keyword:
            return name
        # Busca la palabra clave seguida de guiones/guiones_bajos y bloques alfanuméricos cortos (hasta 3 letras/números)
        pattern = r'(?i)(' + re.escape(keyword) + r'(?:[_\s-]+[A-Za-z0-9]{1,3})*)'
        match = re.search(pattern, name)
        if match:
            return match.group(1).strip('_ -')
        return '\xff' + name

    def _arrange_columns_by_keyword(self):
        """Organiza los tiles en columnas según las variantes de la palabra clave."""
        keyword = self.auto_tile_sort_keyword_var.get().strip() if hasattr(self, 'auto_tile_sort_keyword_var') else ''
        if not keyword:
            messagebox.showinfo("Info", "Escribe una palabra clave (ej: TRAMO, CARRIL) para detectar columnas.")
            return

        if not self.auto_tile_records_full:
            return

        # 1. Agrupar los tiles por la variante de la palabra (ej: TRAMO_02_01)
        variants = {}
        for rec in self.auto_tile_records_full:
            name = rec.get('name', '')
            variant = self._extract_keyword_variant(name, keyword)
            if variant not in variants:
                variants[variant] = []
            variants[variant].append(rec)

        sorted_variants = sorted(variants.keys(), key=RoadImageProcessor._natural_sort_key)
        
        # Eliminar las variantes que no contienen la palabra (empiezan con \xff)
        valid_variants = [v for v in sorted_variants if not v.startswith('\xff')]
        invalid_variants = [v for v in sorted_variants if v.startswith('\xff')]
        
        if not valid_variants:
            messagebox.showinfo("Info", f"No se encontró la palabra '{keyword}' en las imágenes.")
            return

        num_columns = len(valid_variants)

        # Ordenar internamente cada columna por nombre para alinear las filas correctamente
        nat_key = RoadImageProcessor._natural_sort_key
        for v in valid_variants:
            variants[v].sort(key=lambda r: nat_key(r.get('name', '')))

        # Intercalar (zip_longest) para formar las filas del mosaico
        from itertools import zip_longest
        interleaved = []
        lists_to_zip = [variants[v] for v in valid_variants]
        
        for row_tuple in zip_longest(*lists_to_zip):
            for item in row_tuple:
                if item is not None:
                    interleaved.append(item)
                else:
                    # Relleno vacío para mantener la estructura de tabla
                    interleaved.append({'path': None, 'name': '(vacio)', 'size': '-', 'folder': '', 'index': -1})

        # Añadir al final las que no coincidían con el keyword
        for inv_v in invalid_variants:
            variants[inv_v].sort(key=lambda r: nat_key(r.get('name', '')))
            interleaved.extend(variants[inv_v])

        self.auto_tile_records_full = interleaved
        
        # Ajustar el número de columnas global automáticamente
        if hasattr(self, 'join_columns'):
            self.join_columns.set(num_columns)

        if hasattr(self, 'auto_tile_sort_info'):
            self.auto_tile_sort_info.config(text=f"{num_columns} columnas detectadas")

        self._apply_auto_tile_filters()
        self._log_join(f"Tiles organizados en {num_columns} columnas usando la palabra '{keyword}'")

    def _reset_auto_tile_sort(self):
        """Restaura el orden original y limpia indicadores."""
        self.auto_tile_sort_ascending = True
        if hasattr(self, 'auto_tile_sort_var'):
            self.auto_tile_sort_var.set('Original')
        if hasattr(self, 'auto_tile_sort_dir_var'):
            self.auto_tile_sort_dir_var.set('▲ Asc')
        if hasattr(self, 'auto_tile_sort_keyword_var'):
            self.auto_tile_sort_keyword_var.set('')
        if hasattr(self, 'auto_tile_sort_info'):
            self.auto_tile_sort_info.config(text="")
        self._sort_auto_tiles()

    # ---------- Ordenamiento por columna (click en encabezado) ----------

    def _treeview_sort_column(self, tree, col, sort_state, col_labels):
        """Ordena un Treeview genérico al hacer click en el encabezado de columna.
        Retorna la lista de items en el nuevo orden y la dirección usada.
        """
        # Determinar dirección: si ya estaba ordenado por esta columna, invertir
        ascending = not sort_state.get(col, False)
        sort_state.clear()
        sort_state[col] = ascending

        # Obtener todos los items
        items = [(tree.set(iid, col), iid) for iid in tree.get_children('')]

        # Ordenamiento natural (números como números)
        nat_key = RoadImageProcessor._natural_sort_key
        items.sort(key=lambda x: nat_key(x[0]), reverse=not ascending)

        # Reordenar en el treeview
        for index, (_, iid) in enumerate(items):
            tree.move(iid, '', index)

        # Actualizar indicadores en los encabezados
        arrow = ' ▲' if ascending else ' ▼'
        for c, label in col_labels.items():
            if c == col:
                tree.heading(c, text=f"{label}{arrow}")
            else:
                tree.heading(c, text=label)

        return [iid for _, iid in items], ascending

    def _sort_auto_tiles_by_column(self, col):
        """Ordena la tabla de tiles del grupo al hacer click en el encabezado."""
        col_labels = {'orden': '#', 'archivo': 'Archivo', 'tamano': 'Tamano', 'indice': 'Ind.'}
        ordered_iids, ascending = self._treeview_sort_column(
            self.auto_tiles_tree, col, self._auto_tiles_col_sort_state, col_labels
        )
        # Sincronizar la lista de datos con el nuevo orden visual
        reordered = []
        for iid in ordered_iids:
            idx = int(iid)
            if 0 <= idx < len(self.auto_tile_records):
                reordered.append(self.auto_tile_records[idx])
        if reordered:
            self.auto_tile_records = reordered
            # También actualizar la lista completa para mantener coherencia
            self.auto_tile_records_full = list(reordered)
            self._refresh_auto_tiles_tree()

    def _sort_join_tree_by_column(self, col):
        """Ordena la tabla de grupos detectados al hacer click en el encabezado."""
        col_labels = {'grupo': 'Grupo', 'carpeta': 'Carpeta', 'tiles': 'Imgs',
                      'tamano': 'Tamano', 'salida': 'Salida'}
        ordered_iids, _ = self._treeview_sort_column(
            self.join_tree, col, self._join_tree_sort_state, col_labels
        )
        # Reordenar la lista de datos de grupos
        if hasattr(self, 'join_groups') and self.join_groups:
            reordered = []
            for iid in ordered_iids:
                try:
                    idx = int(iid)
                    if 0 <= idx < len(self.join_groups):
                        reordered.append(self.join_groups[idx])
                except (ValueError, IndexError):
                    pass
            if reordered:
                self.join_groups = reordered
                self._refresh_join_groups_tree()

    def _move_auto_tile(self, direction):
        """Sube o baja los tiles seleccionados en la lista auto."""
        selected = sorted(int(item) for item in self.auto_tiles_tree.selection())
        if not selected or not self.auto_tile_records:
            return

        if direction < 0 and selected[0] == 0:
            return
        if direction > 0 and selected[-1] == len(self.auto_tile_records) - 1:
            return

        selected_set = set(selected)
        moving = [self.auto_tile_records[i] for i in selected]
        remaining = [rec for i, rec in enumerate(self.auto_tile_records) if i not in selected_set]

        insert_pos = selected[0] - 1 if direction < 0 else selected[0] + 1
        self.auto_tile_records = remaining[:insert_pos] + moving + remaining[insert_pos:]
        new_indices = list(range(insert_pos, insert_pos + len(moving)))
        self._refresh_auto_tiles_tree(new_indices)

    def _generate_auto_mosaic_preview(self):
        """Genera el mosaico con los tiles del visor auto y lo muestra."""
        if not self.auto_tile_records:
            messagebox.showinfo("Info", "Selecciona un grupo primero")
            return

        columns = max(0, self.join_columns.get())
        spacing = max(0, self.join_spacing.get())
        paths = [rec['path'] for rec in self.auto_tile_records]
        real_paths = [path for path in paths if path]

        if not real_paths:
            messagebox.showinfo("Info", "El grupo no tiene imagenes validas")
            return

        if columns <= 0:
            columns = 1  # Vertical por defecto (pavimento)
        else:
            columns = min(columns, len(paths))
        rows = math.ceil(len(paths) / columns)

        self.auto_mosaic_info_label.config(text="Generando mosaico...")
        self.root.update_idletasks()

        try:
            sizes = []
            for path in real_paths:
                with Image.open(path) as img:
                    sizes.append(img.size)

            cell_w = max(w for w, _ in sizes)
            cell_h = max(h for _, h in sizes)
            joined_w = columns * cell_w + spacing * (columns - 1)
            joined_h = rows * cell_h + spacing * (rows - 1)

            MAX_PIXELS = 200_000_000
            total_px = joined_w * joined_h
            if total_px > MAX_PIXELS:
                scale_down = math.sqrt(MAX_PIXELS / total_px)
                joined_w = int(joined_w * scale_down)
                joined_h = int(joined_h * scale_down)
                cell_w = int(cell_w * scale_down)
                cell_h = int(cell_h * scale_down)
                spacing = int(spacing * scale_down)

            canvas_img = Image.new("RGB", (joined_w, joined_h), (255, 255, 255))

            for idx, path in enumerate(paths):
                row = idx // columns
                col = idx % columns
                x = col * (cell_w + spacing)
                y = row * (cell_h + spacing)

                if not path:
                    continue

                with Image.open(path) as img:
                    tile = img.convert("RGB")
                    if tile.size != (cell_w, cell_h):
                        tile = tile.resize((cell_w, cell_h), Image.LANCZOS)
                    canvas_img.paste(tile, (x, y))

            self.auto_mosaic_pil = canvas_img
            self.auto_mosaic_zoom = 1.0

            self._fit_auto_mosaic_to_canvas()
            self.btn_auto_save_mosaic.config(state=tk.NORMAL)

            info = f"Mosaico: {joined_w}x{joined_h}px | {columns} col x {rows} filas | {len(real_paths)} tiles"
            if len(real_paths) != len(paths):
                info += f" | {len(paths) - len(real_paths)} vacios"
            self.auto_mosaic_info_label.config(text=info)
            self._log_join(f"Vista previa auto generada: {info}")

        except Exception as e:
            self.auto_mosaic_info_label.config(text=f"Error: {e}")
            import traceback
            self._log_join(f"Error generando mosaico auto:\n{traceback.format_exc()}")

    def _fit_auto_mosaic_to_canvas(self):
        """Ajusta el zoom del mosaico auto para que quepa en el canvas."""
        if self.auto_mosaic_pil is None:
            return

        self.auto_mosaic_canvas.update_idletasks()
        canvas_w = max(240, self.auto_mosaic_canvas.winfo_width())
        canvas_h = max(220, self.auto_mosaic_canvas.winfo_height())

        img_w, img_h = self.auto_mosaic_pil.size
        scale_x = (canvas_w - 20) / img_w if img_w > 0 else 1.0
        scale_y = (canvas_h - 20) / img_h if img_h > 0 else 1.0
        self.auto_mosaic_zoom = min(scale_x, scale_y, 1.0)

        self._render_auto_mosaic_at_zoom()

    def _render_auto_mosaic_at_zoom(self):
        """Renderiza el mosaico auto en el canvas al nivel de zoom actual."""
        if self.auto_mosaic_pil is None:
            return

        img_w, img_h = self.auto_mosaic_pil.size
        display_w = max(1, int(img_w * self.auto_mosaic_zoom))
        display_h = max(1, int(img_h * self.auto_mosaic_zoom))

        resized = self.auto_mosaic_pil.resize(
            (display_w, display_h),
            Image.LANCZOS if self.auto_mosaic_zoom < 1.0 else Image.NEAREST
        )

        self.auto_mosaic_photo = ImageTk.PhotoImage(resized)
        self.auto_mosaic_canvas.delete("all")
        self.auto_mosaic_canvas.create_image(0, 0, anchor=tk.NW, image=self.auto_mosaic_photo)
        self.auto_mosaic_canvas.config(scrollregion=(0, 0, display_w, display_h))

        self.auto_mosaic_zoom_label.config(text=f"{int(self.auto_mosaic_zoom * 100)}%")

    def _zoom_auto_mosaic(self, factor):
        """Aplica zoom al mosaico auto."""
        if self.auto_mosaic_pil is None:
            return
        new_zoom = self.auto_mosaic_zoom * factor
        new_zoom = max(0.02, min(5.0, new_zoom))
        self.auto_mosaic_zoom = new_zoom
        self._render_auto_mosaic_at_zoom()

    def _reset_auto_mosaic_zoom(self):
        """Resetea el zoom del mosaico auto."""
        if self.auto_mosaic_pil is None:
            return
        self._fit_auto_mosaic_to_canvas()

    def _on_auto_mosaic_mousewheel(self, event):
        """Zoom con rueda en el mosaico auto."""
        if self.auto_mosaic_pil is None:
            return
        if event.delta > 0:
            self._zoom_auto_mosaic(1.15)
        else:
            self._zoom_auto_mosaic(0.85)

    def _on_auto_mosaic_pan_start(self, event):
        """Inicia pan en el mosaico auto."""
        self.auto_mosaic_drag_x = event.x
        self.auto_mosaic_drag_y = event.y

    def _on_auto_mosaic_pan_drag(self, event):
        """Pan del mosaico auto."""
        dx = event.x - self.auto_mosaic_drag_x
        dy = event.y - self.auto_mosaic_drag_y
        self.auto_mosaic_canvas.xview_scroll(-int(dx), "units")
        self.auto_mosaic_canvas.yview_scroll(-int(dy), "units")
        self.auto_mosaic_drag_x = event.x
        self.auto_mosaic_drag_y = event.y

    def _save_auto_mosaic_result(self):
        """Guarda el mosaico del visor auto."""
        if self.auto_mosaic_pil is None:
            messagebox.showinfo("Info", "Genera la vista previa primero")
            return

        output_dir = self._get_join_output_dir()
        os.makedirs(output_dir, exist_ok=True)

        # Obtener nombre del grupo
        group_name = "join_auto"
        if self.auto_selected_group_idx is not None:
            try:
                group = self.join_groups[self.auto_selected_group_idx]
                group_name = group.get('display_name', 'join_auto')
            except (IndexError, KeyError):
                pass

        safe_name = RoadImageProcessor._safe_filename(group_name)
        output_name = f"{safe_name}_join.png"
        output_path = os.path.join(output_dir, output_name)

        if os.path.exists(output_path):
            counter = 1
            while os.path.exists(output_path):
                output_name = f"{safe_name}_join_{counter:03d}.png"
                output_path = os.path.join(output_dir, output_name)
                counter += 1

        # Reconstruir a tamano completo para guardar
        columns = max(0, self.join_columns.get())
        spacing = max(0, self.join_spacing.get())
        paths = [rec['path'] for rec in self.auto_tile_records]
        real_paths = [path for path in paths if path]

        if columns <= 0:
            columns = 1  # Vertical por defecto
        else:
            columns = min(columns, len(paths))

        # Construir grupo para join_tile_group
        group_data = {
            'display_name': group_name,
            'folder': os.path.dirname(real_paths[0]) if real_paths else output_dir,
            'prefix': safe_name,
            'tile_count': len(real_paths),
            'cell_count': len(paths),
            'tile_items': [(rec['index'], rec['path']) for rec in self.auto_tile_records],
            'tile_indices': [rec['index'] for rec in self.auto_tile_records],
            'paths': paths,
            'output_name': output_name
        }

        try:
            self.auto_mosaic_info_label.config(text="Guardando imagen final...")
            self.root.update_idletasks()

            saved_path = RoadImageProcessor.join_tile_group(
                group_data,
                output_dir,
                columns,
                spacing,
                progress_callback=self._log_join
            )
            self._log_join(f"Guardado exitosamente: {saved_path}")
            self.auto_mosaic_info_label.config(text=f"Guardado: {saved_path}")
            messagebox.showinfo(
                "Guardado exitosamente",
                f"Imagen guardada en:\n{saved_path}"
            )
        except Exception as e:
            self._log_join(f"Error al guardar: {e}")
            messagebox.showerror("Error", f"No se pudo guardar:\n{e}")

    def _get_selected_join_groups(self):
        selected = self.join_tree.selection()
        if not selected:
            return []
        groups = []
        for item_id in selected:
            try:
                groups.append(self.join_groups[int(item_id)])
            except (ValueError, IndexError):
                pass
        return groups

    def _start_join_selected(self):
        groups = self._get_selected_join_groups()
        if not groups:
            messagebox.showinfo("Info", "Selecciona uno o mas grupos para juntar")
            return
        self._start_join(groups)

    def _start_join_all(self):
        if not self.join_groups:
            self._scan_join_groups()
        if self.join_groups:
            self._start_join(self.join_groups)

    def _start_join(self, groups):
        if self.join_processing:
            return

        output_dir = self._get_join_output_dir()
        columns = max(0, self.join_columns.get())
        spacing = max(0, self.join_spacing.get())
        start_index = max(0, self.join_start_index.get())
        end_index = self.join_end_index.get()
        batch_size = max(0, self.join_batch_size.get())

        join_batches = []
        for group in groups:
            join_batches.extend(RoadImageProcessor.build_join_batches(
                group,
                start_index,
                end_index,
                batch_size
            ))

        if not join_batches:
            messagebox.showinfo("Sin imagenes", "No hay imagenes dentro del rango indicado")
            return

        end_text = "ultimo" if end_index < 0 else str(end_index)
        batch_text = "todo el rango" if batch_size == 0 else f"de {batch_size} en {batch_size}"
        msg = f"Se juntaran {len(groups)} grupos en {len(join_batches)} imagenes join.\n\n"
        msg += f"Rango: {start_index} a {end_text}\n"
        msg += f"Intervalo: {batch_text}\n\n"
        msg += f"Salida:\n{output_dir}\n\nContinuar?"
        if not messagebox.askyesno("Confirmar Join", msg):
            return

        self.join_processing = True
        self._set_join_buttons_state(False)

        def run_join():
            saved_paths = []
            try:
                os.makedirs(output_dir, exist_ok=True)
                self._log_join("="*60)
                self._log_join("JOIN DE RECORTES")
                self._log_join("="*60)
                self._log_join(f"Grupos: {len(groups)} | Joins a generar: {len(join_batches)}")
                self._log_join(f"Rango: {start_index} a {end_text} | Intervalo: {batch_text}")
                self._log_join(f"Columnas: {'auto' if columns == 0 else columns} | Separacion: {spacing}px")

                for idx, group in enumerate(join_batches, 1):
                    self._log_join(f"\n[{idx}/{len(join_batches)}] {group['display_name']}")
                    self._log_join(f"  Imagenes: {group['tile_count']} | Tamano: {group['tile_size']}")

                    output_path = RoadImageProcessor.join_tile_group(
                        group,
                        output_dir,
                        columns,
                        spacing,
                        progress_callback=self._log_join
                    )
                    saved_paths.append(output_path)
                    self._log_join(f"  Guardado: {output_path}")

                self._log_join("\n" + "="*60)
                self._log_join(f"Completado: {len(saved_paths)} imagenes join")
                self._log_join("="*60)
                self.root.after(0, lambda: messagebox.showinfo(
                    "Join completado",
                    f"Se generaron {len(saved_paths)} imagenes en:\n{output_dir}"
                ))
            except Exception as e:
                self._log_join(f"\nERROR JOIN: {str(e)}")
                import traceback
                self._log_join(traceback.format_exc())
                self.root.after(0, lambda: messagebox.showerror("Error Join", str(e)))
            finally:
                self.join_processing = False
                self.root.after(0, lambda: self._set_join_buttons_state(bool(self.join_groups)))

        thread = threading.Thread(target=run_join)
        thread.daemon = True
        thread.start()

    def _log_join(self, message):
        def add_text():
            self.join_status_text.insert(tk.END, message + "\n")
            self.join_status_text.see(tk.END)

        self.root.after(0, add_text)

    # ==================== Métodos de ángulo con spinbox ====================

    def _adjust_angle(self, delta):
        """Ajusta el ángulo con delta"""
        current = self.manual_angle.get()
        new_angle = current + delta
        
        while new_angle > 180:
            new_angle -= 360
        while new_angle < -180:
            new_angle += 360
        
        self.manual_angle.set(round(new_angle, 2))
        self.angle_label.config(text=f"{new_angle:.2f}°")
        self._update_preview()
    
    # ==================== Métodos de zoom ====================
    
    def _zoom_preview(self, factor):
        new_zoom = self.zoom_level.get() * factor
        new_zoom = max(0.1, min(10.0, new_zoom))
        self.zoom_level.set(new_zoom)
        self.zoom_label.config(text=f"Zoom: {int(new_zoom * 100)}%")
        self._update_preview()
    
    def _reset_zoom(self):
        self.zoom_level.set(1.0)
        self.zoom_label.config(text="Zoom: 100%")
        self.preview_offset_x = 0
        self.preview_offset_y = 0
        self._update_preview()
    
    def _calcular_tile_por_cortes(self):
        """Calcula el tamaño de tile para que la imagen se divida exactamente en N cortes (solo esta imagen)"""
        if not self.current_preview_filepath or self.current_preview_image is None:
            messagebox.showinfo("Info", "Selecciona una imagen primero en la lista de polígonos")
            return

        h_img, w_img = self.current_preview_image.shape[:2]
        num_x = self.num_cuts_x.get()
        num_y = self.num_cuts_y.get()
        filepath = self.current_preview_filepath
        overlap = self.configuraciones[filepath].get('overlap', self.overlap_global.get())

        if num_x <= 0 or num_y <= 0:
            messagebox.showwarning("Advertencia", "La cantidad de cortes debe ser mayor a 0")
            return

        # tile_size = (image_size + overlap * (num - 1)) / num
        tile_x = math.ceil((w_img + overlap * (num_x - 1)) / num_x)
        tile_y = math.ceil((h_img + overlap * (num_y - 1)) / num_y)

        # Solo guardar en la config individual de esta imagen
        self.configuraciones[filepath]['tile_size_x'] = tile_x
        self.configuraciones[filepath]['tile_size_y'] = tile_y
        self.configuraciones[filepath]['_has_custom_tiles'] = True
        self._update_tree_config_item(filepath)
        self._update_preview()

        nombre = os.path.basename(filepath)
        self._log(f"Cortes exactos ({nombre}): {num_x}x{num_y} → Tile {tile_x}x{tile_y}px")

    def _update_thumbnail(self, filepath):
        """Actualiza la miniatura mostrando la imagen final procesada (igual que vista previa)"""
        try:
            if self.current_preview_image is None:
                self._clear_thumbnail()
                return

            src = self.current_preview_image
            h_src, w_src = src.shape[:2]

            # Obtener tamano disponible del canvas de miniatura
            self.thumbnail_canvas.update_idletasks()
            cw = self.thumbnail_canvas.winfo_width()
            ch = self.thumbnail_canvas.winfo_height()
            if cw <= 1:
                cw = 280
            if ch <= 1:
                ch = 280

            # Escalar manteniendo proporcion para ajustar al canvas
            scale = min(cw / w_src, ch / h_src)
            new_w = max(1, int(w_src * scale))
            new_h = max(1, int(h_src * scale))
            thumb = cv2.resize(src, (new_w, new_h), interpolation=cv2.INTER_AREA)

            # Dibujar cuadricula y solapamiento en la miniatura
            config = self.configuraciones.get(filepath, {})
            tile_x = config.get('tile_size_x', self.tile_size_x_global.get())
            tile_y = config.get('tile_size_y', self.tile_size_y_global.get())
            overlap = config.get('overlap', self.overlap_global.get())

            if self.show_grid.get() or self.show_overlap.get():
                step_x = tile_x - overlap
                step_y = tile_y - overlap
                if step_x > 0 and step_y > 0:
                    num_tiles_x = math.ceil((w_src - overlap) / step_x)
                    num_tiles_y = math.ceil((h_src - overlap) / step_y)

                    for idx_y in range(num_tiles_y):
                        for idx_x in range(num_tiles_x):
                            x = idx_x * step_x
                            y = idx_y * step_y
                            x_end = min(x + tile_x, w_src)
                            y_end = min(y + tile_y, h_src)

                            is_adjusted = False
                            if x_end == w_src and (x_end - x) < tile_x:
                                x = max(0, w_src - tile_x)
                                x_end = w_src
                                if idx_x > 0:
                                    is_adjusted = True
                            if y_end == h_src and (y_end - y) < tile_y:
                                y = max(0, h_src - tile_y)
                                y_end = h_src
                                if idx_y > 0:
                                    is_adjusted = True

                            if is_adjusted and self.skip_last_tile.get():
                                continue

                            # Coordenadas escaladas a la miniatura
                            sx = int(x * scale)
                            sy = int(y * scale)
                            sx_end = int(x_end * scale)
                            sy_end = int(y_end * scale)

                            tile_color = (255, 0, 0) if is_adjusted else (0, 255, 0)

                            if self.show_overlap.get() and overlap > 0:
                                ov = thumb.copy()
                                if idx_x < num_tiles_x - 1:
                                    ox = int((x_end - overlap) * scale)
                                    cv2.rectangle(ov, (ox, sy), (sx_end, sy_end), (255, 255, 0), -1)
                                if idx_y < num_tiles_y - 1:
                                    oy = int((y_end - overlap) * scale)
                                    cv2.rectangle(ov, (sx, oy), (sx_end, sy_end), (255, 255, 0), -1)
                                cv2.addWeighted(ov, 0.3, thumb, 0.7, 0, thumb)

                            if self.show_grid.get():
                                cv2.rectangle(thumb, (sx, sy), (sx_end, sy_end), tile_color, 1)

            pil_img = Image.fromarray(thumb)
            self.thumbnail_photo = ImageTk.PhotoImage(pil_img)

            self.thumbnail_canvas.delete("all")
            x_off = (cw - new_w) // 2
            y_off = (ch - new_h) // 2
            self.thumbnail_canvas.create_image(x_off, y_off, anchor=tk.NW, image=self.thumbnail_photo)

            self.thumbnail_size_label.config(text=f"Final: {w_src} x {h_src} px")
        except Exception as e:
            print(f"Error miniatura: {e}")

    def _clear_thumbnail(self):
        """Limpia la miniatura cuando no hay imagen seleccionada"""
        self.thumbnail_canvas.delete("all")
        self.thumbnail_photo = None
        self.thumbnail_size_label.config(text="")

    def _on_mousewheel(self, event):
        """Scroll vertical con rueda del mouse"""
        scroll_amount = -1 if event.delta > 0 else 1
        self.preview_canvas.yview_scroll(scroll_amount * 3, "units")

    def _on_shift_mousewheel(self, event):
        """Scroll horizontal con Shift + rueda del mouse"""
        scroll_amount = -1 if event.delta > 0 else 1
        self.preview_canvas.xview_scroll(scroll_amount * 3, "units")

    def _on_ctrl_mousewheel(self, event):
        """Zoom con Ctrl + rueda del mouse"""
        if event.delta > 0:
            self._zoom_preview(1.1)
        else:
            self._zoom_preview(0.9)
    
    def _on_mouse_motion(self, event):
        if not self.show_pixel_info.get() or self.current_preview_image is None:
            self.pixel_info_label.config(text="")
            return
        
        try:
            zoom = self.zoom_level.get()
            x_img = int(event.x / zoom)
            y_img = int(event.y / zoom)
            
            h, w = self.current_preview_image.shape[:2]
            
            if 0 <= x_img < w and 0 <= y_img < h:
                pixel = self.current_preview_image[y_img, x_img]
                r, g, b = int(pixel[0]), int(pixel[1]), int(pixel[2])
                
                self.pixel_info_label.config(
                    text=f"📍 X:{x_img} Y:{y_img} | RGB:({r},{g},{b}) | #{r:02x}{g:02x}{b:02x}"
                )
            else:
                self.pixel_info_label.config(text="")
        except:
            self.pixel_info_label.config(text="")
    
    def _on_canvas_click(self, event):
        self.drag_start_x = event.x
        self.drag_start_y = event.y
    
    def _on_canvas_drag(self, event):
        dx = event.x - self.drag_start_x
        dy = event.y - self.drag_start_y

        self.preview_canvas.xview_scroll(-int(dx), "units")
        self.preview_canvas.yview_scroll(-int(dy), "units")

        self.drag_start_x = event.x
        self.drag_start_y = event.y
    
    # ==================== Preview CON SOLAPAMIENTO ====================
    
    def _update_preview(self):
        """Actualiza preview CON SOLAPAMIENTO VISIBLE"""
        if not self.current_preview_filepath:
            return
        
        try:
            filepath = self.current_preview_filepath
            config = self.configuraciones[filepath]
            polygon = config.get('polygon')
            angle = self.manual_angle.get()
            
            # Config de esta imagen
            tile_x = config.get('tile_size_x', self.tile_size_x_global.get())
            tile_y = config.get('tile_size_y', self.tile_size_y_global.get())
            overlap = config.get('overlap', self.overlap_global.get())
            
            # Cargar y procesar imagen
            img = cv2.imread(filepath)
            if img is None:
                return
            
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            # Polígono
            if polygon and len(polygon) >= 3:
                mask = np.zeros(img.shape[:2], dtype=np.uint8)
                pts = np.array(polygon, np.int32)
                cv2.fillPoly(mask, [pts], 255)
                
                result = np.ones_like(img) * 255
                result[mask == 255] = img[mask == 255]
                
                x_coords = [p[0] for p in polygon]
                y_coords = [p[1] for p in polygon]
                x_min, x_max = max(0, min(x_coords)), min(img.shape[1], max(x_coords))
                y_min, y_max = max(0, min(y_coords)), min(img.shape[0], max(y_coords))
                
                cropped = result[y_min:y_max, x_min:x_max]
            else:
                cropped = img
            
            # Rotar
            h, w = cropped.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            
            cos = np.abs(M[0, 0])
            sin = np.abs(M[0, 1])
            new_w = int((h * sin) + (w * cos))
            new_h = int((h * cos) + (w * sin))
            
            M[0, 2] += (new_w / 2) - center[0]
            M[1, 2] += (new_h / 2) - center[1]
            
            rotated = cv2.warpAffine(cropped, M, (new_w, new_h),
                                    borderMode=cv2.BORDER_CONSTANT,
                                    borderValue=(255, 255, 255))
            
            # Bordes blancos
            final_image, stats = RoadImageProcessor.eliminar_bordes_blancos(rotated)

            # Guardar para píxeles
            self.current_preview_image = final_image.copy()
            
            # DIBUJAR CUADRÍCULA Y SOLAPAMIENTO
            if self.show_grid.get() or self.show_overlap.get():
                preview_img = final_image.copy()
                h_img, w_img = preview_img.shape[:2]
                
                step_x = tile_x - overlap
                step_y = tile_y - overlap
                
                num_tiles_x = math.ceil((w_img - overlap) / step_x)
                num_tiles_y = math.ceil((h_img - overlap) / step_y)
                
                tile_count = 0
                for idx_y in range(num_tiles_y):
                    for idx_x in range(num_tiles_x):
                        x = idx_x * step_x
                        y = idx_y * step_y

                        x_end = min(x + tile_x, w_img)
                        y_end = min(y + tile_y, h_img)

                        # Detectar si es tile ajustado al borde (solapamiento grande)
                        is_adjusted_x = False
                        is_adjusted_y = False

                        # Ajustar para tiles completos en bordes
                        if x_end == w_img and (x_end - x) < tile_x:
                            x = max(0, w_img - tile_x)
                            x_end = w_img
                            if idx_x > 0:
                                is_adjusted_x = True

                        if y_end == h_img and (y_end - y) < tile_y:
                            y = max(0, h_img - tile_y)
                            y_end = h_img
                            if idx_y > 0:
                                is_adjusted_y = True

                        is_large_overlap = is_adjusted_x or is_adjusted_y

                        # Omitir tile con solapamiento grande si está activada la opción
                        if is_large_overlap and self.skip_last_tile.get():
                            continue

                        # Color: rojo si tiene solapamiento grande, verde si es normal
                        tile_color = (255, 0, 0) if is_large_overlap else (0, 255, 0)

                        # DIBUJAR SOLAPAMIENTO (semi-transparente amarillo/rojo)
                        if self.show_overlap.get() and overlap > 0:
                            overlay = preview_img.copy()

                            # Solapamiento derecho
                            if idx_x < num_tiles_x - 1:
                                overlap_x_start = x_end - overlap
                                cv2.rectangle(overlay,
                                            (overlap_x_start, y),
                                            (x_end, y_end),
                                            (255, 255, 0), -1)

                            # Solapamiento inferior
                            if idx_y < num_tiles_y - 1:
                                overlap_y_start = y_end - overlap
                                cv2.rectangle(overlay,
                                            (x, overlap_y_start),
                                            (x_end, y_end),
                                            (255, 255, 0), -1)

                            cv2.addWeighted(overlay, 0.3, preview_img, 0.7, 0, preview_img)

                        # DIBUJAR CUADRÍCULA
                        if self.show_grid.get():
                            cv2.rectangle(preview_img, (x, y), (x_end, y_end),
                                        tile_color, 2)

                            tile_count += 1
                            text_pos = (x + 10, y + 30)
                            cv2.putText(preview_img, f"#{tile_count}", text_pos,
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, tile_color, 2)
                
                final_image = preview_img
            
            # Zoom
            zoom = self.zoom_level.get()
            if zoom != 1.0:
                h, w = final_image.shape[:2]
                new_w = int(w * zoom)
                new_h = int(h * zoom)
                final_image = cv2.resize(final_image, (new_w, new_h), 
                                       interpolation=cv2.INTER_LINEAR if zoom > 1 else cv2.INTER_AREA)
            
            # Mostrar
            pil_img = Image.fromarray(final_image)
            self.preview_photo = ImageTk.PhotoImage(pil_img)
            
            self.preview_canvas.delete("all")
            self.preview_canvas.create_image(0, 0, anchor=tk.NW, image=self.preview_photo)
            self.preview_canvas.config(scrollregion=(0, 0, final_image.shape[1], final_image.shape[0]))
            
            # Info
            h_img, w_img = self.current_preview_image.shape[:2]
            step_x = tile_x - overlap
            step_y = tile_y - overlap
            num_tiles_x = math.ceil((w_img - overlap) / step_x)
            num_tiles_y = math.ceil((h_img - overlap) / step_y)
            tile_count = num_tiles_x * num_tiles_y

            info_text = f"Ángulo: {angle:.2f}° | {w_img}x{h_img}px | Tiles:{tile_x}x{tile_y} Overlap:{overlap} | {tile_count} tiles | Zoom:{int(zoom*100)}%"

            self.preview_info_label.config(text=info_text)

            # Actualizar spinboxes de cortes exactos con valores actuales
            self.num_cuts_x.set(num_tiles_x)
            self.num_cuts_y.set(num_tiles_y)

            # Guardar dimensiones de imagen procesada para cálculo de recortes
            self.configuraciones[filepath]['_preview_w'] = w_img
            self.configuraciones[filepath]['_preview_h'] = h_img

            self._update_tree_config_item(filepath)

            # Actualizar miniatura con recortes visibles
            self._update_thumbnail(filepath)

        except Exception as e:
            print(f"Error preview: {e}")
            import traceback
            traceback.print_exc()
    
    # ==================== Métodos de rotación ====================
    
    def _quick_rotate(self, degrees):
        current = self.manual_angle.get()
        new_angle = (current + degrees) % 360
        if new_angle > 180:
            new_angle -= 360
        self.manual_angle.set(new_angle)
        self.angle_label.config(text=f"{new_angle:.2f}°")
        self._update_preview()
    
    def _auto_rotate(self):
        if not self.current_preview_filepath:
            messagebox.showinfo("Info", "Selecciona una imagen primero")
            return
        
        puntos = self.configuraciones[self.current_preview_filepath].get('puntos')
        if not puntos or len(puntos) != 2:
            messagebox.showinfo("Info", "Define primero los puntos del eje")
            return
        
        angle = RoadImageProcessor.calcular_angulo_rotacion(puntos[0], puntos[1])
        self.manual_angle.set(round(angle, 2))
        self.angle_label.config(text=f"{angle:.2f}°")
        self._update_preview()
        self._log(f"Rotación automática: {angle:.2f}°")
    
    def _reset_angle(self):
        self.manual_angle.set(0.0)
        self.angle_label.config(text="0.00°")
        self._update_preview()
    
    def _save_manual_rotation(self):
        if not self.current_preview_filepath:
            messagebox.showinfo("Info", "Selecciona una imagen primero")
            return
        
        angle = self.manual_angle.get()
        self.configuraciones[self.current_preview_filepath]['angulo_manual'] = angle
        
        nombre = os.path.basename(self.current_preview_filepath)
        for item_id in self.tree_polygons.get_children():
            item_vals = list(self.tree_polygons.item(item_id)['values'])
            if item_vals[1] == nombre:
                item_vals[3] = f"✓ {angle:.1f}°"
                self.tree_polygons.item(item_id, values=item_vals)
                break
        
        # Cambiar color a verde para indicar que ya fue guardada
        self._set_save_rotation_button_state(enabled=True, angle=angle)
        self._log(f"Rotación guardada para {nombre}: {angle:.2f}°")

    def _save_skip_last_tile(self):
        """Guarda omitir último recorte en la config de la imagen actual"""
        if self.current_preview_filepath:
            self.configuraciones[self.current_preview_filepath]['skip_last_tile'] = self.skip_last_tile.get()
        self._update_preview()

    # ==================== Config individual ====================
    
    def _on_config_tree_select(self, event=None):
        """Al seleccionar una imagen en Configuración Individual, carga sus valores en los spinboxes globales"""
        selection = self.tree_config.selection()
        if not selection:
            return

        item = self.tree_config.item(selection[0])
        nombre_imagen = item['values'][1]

        filepath = None
        for fp in self.imagenes:
            if os.path.basename(fp) == nombre_imagen:
                filepath = fp
                break

        if not filepath or filepath not in self.configuraciones:
            return

        config = self.configuraciones[filepath]
        # Suprimir trace para evitar que al cargar valores sobreescriba configs de otras imágenes
        self._suppressing_trace = True
        self.tile_size_x_global.set(config.get('tile_size_x', self.tile_size_x_global.get()))
        self.tile_size_y_global.set(config.get('tile_size_y', self.tile_size_y_global.get()))
        self.overlap_global.set(config.get('overlap', self.overlap_global.get()))
        self._suppressing_trace = False

    def _update_tree_config_item(self, filepath):
        """Actualiza la fila del treeview de config para un filepath dado"""
        nombre = os.path.basename(filepath)
        config = self.configuraciones[filepath]
        num_recortes = self._calcular_num_recortes(filepath)
        for item_id in self.tree_config.get_children():
            item_vals = self.tree_config.item(item_id)['values']
            if item_vals[1] == nombre:
                self.tree_config.item(item_id,
                                     values=(item_vals[0], nombre,
                                            config.get('tile_size_x', self.tile_size_x_global.get()),
                                            config.get('tile_size_y', self.tile_size_y_global.get()),
                                            config.get('overlap', self.overlap_global.get()),
                                            num_recortes))
                break

    def _edit_individual_config(self):
        selection = self.tree_config.selection()
        if not selection:
            messagebox.showinfo("Info", "Selecciona una imagen")
            return

        item = self.tree_config.item(selection[0])
        nombre_imagen = item['values'][1]
        
        filepath = None
        for fp in self.imagenes:
            if os.path.basename(fp) == nombre_imagen:
                filepath = fp
                break
        
        if not filepath:
            return
        
        config_win = ImageConfigWindow(self.root, nombre_imagen, 
                                       self.configuraciones[filepath])
        result = config_win.get_result()
        
        if result:
            self.configuraciones[filepath].update(result)
            self.configuraciones[filepath]['_has_custom_tiles'] = True
            num_recortes = self._calcular_num_recortes(filepath)
            nro = item['values'][0]
            self.tree_config.item(selection[0],
                                 values=(nro, nombre_imagen,
                                        result['tile_size_x'],
                                        result['tile_size_y'],
                                        result['overlap'],
                                        num_recortes))
            
            for item_id in self.tree_images.get_children():
                item_vals = self.tree_images.item(item_id)['values']
                if item_vals[1] == nombre_imagen:
                    config_text = f"{result['tile_size_x']}x{result['tile_size_y']}"
                    self.tree_images.item(item_id,
                                         values=(item_vals[0], item_vals[1], item_vals[2],
                                                config_text, item_vals[4]))
                    break
            
            self._log(f"Config individual: {nombre_imagen}")
            
            if filepath == self.current_preview_filepath:
                self._update_preview()
    
    def _copy_from_global(self):
        selection = self.tree_config.selection()
        if not selection:
            messagebox.showinfo("Info", "Selecciona una imagen")
            return
        
        item = self.tree_config.item(selection[0])
        nro = item['values'][0]
        nombre_imagen = item['values'][1]

        filepath = None
        for fp in self.imagenes:
            if os.path.basename(fp) == nombre_imagen:
                filepath = fp
                break

        if not filepath:
            return

        self.configuraciones[filepath]['tile_size_x'] = self.tile_size_x_global.get()
        self.configuraciones[filepath]['tile_size_y'] = self.tile_size_y_global.get()
        self.configuraciones[filepath]['overlap'] = self.overlap_global.get()
        self.configuraciones[filepath]['_has_custom_tiles'] = False

        num_recortes = self._calcular_num_recortes(filepath)
        self.tree_config.item(selection[0],
                             values=(nro, nombre_imagen,
                                    self.tile_size_x_global.get(),
                                    self.tile_size_y_global.get(),
                                    self.overlap_global.get(),
                                    num_recortes))

        self._log(f"Config global → {nombre_imagen}")
        
        if filepath == self.current_preview_filepath:
            self._update_preview()
    
    def _apply_global_to_all(self):
        if not self.imagenes:
            messagebox.showinfo("Info", "No hay imágenes")
            return
        
        for filepath in self.imagenes:
            self.configuraciones[filepath]['tile_size_x'] = self.tile_size_x_global.get()
            self.configuraciones[filepath]['tile_size_y'] = self.tile_size_y_global.get()
            self.configuraciones[filepath]['overlap'] = self.overlap_global.get()
            self.configuraciones[filepath]['_has_custom_tiles'] = False
        
        self.tree_config.delete(*self.tree_config.get_children())
        for idx, filepath in enumerate(self.imagenes, 1):
            nombre = os.path.basename(filepath)
            config = self.configuraciones[filepath]
            num_recortes = self._calcular_num_recortes(filepath)
            self.tree_config.insert('', tk.END,
                                   values=(idx, nombre,
                                          config['tile_size_x'],
                                          config['tile_size_y'],
                                          config['overlap'],
                                          num_recortes))
        
        self._log("Config global → Todas")
        
        if self.current_preview_filepath:
            self._update_preview()
    
    # ==================== Archivos ====================
    
    def _add_files(self):
        filetypes = (
            ('Imágenes', '*.tif *.tiff *.jpg *.jpeg *.png *.bmp'),
            ('TIF', '*.tif *.tiff'),
            ('JPG', '*.jpg *.jpeg'),
            ('PNG', '*.png'),
            ('Todos', '*.*')
        )
        
        files = filedialog.askopenfilenames(title="Seleccionar Imágenes",
                                           filetypes=filetypes)
        
        if files:
            for file in files:
                self._add_image(file)
    
    def _add_folder(self):
        folder = filedialog.askdirectory(title="Seleccionar Carpeta")
        
        if folder:
            extensions = ['.tif', '.tiff', '.jpg', '.jpeg', '.png', '.bmp']
            folder_path = Path(folder)
            
            count = 0
            for ext in extensions:
                for file in folder_path.glob(f'*{ext}'):
                    self._add_image(str(file))
                    count += 1
                for file in folder_path.glob(f'*{ext.upper()}'):
                    self._add_image(str(file))
                    count += 1
            
            if count > 0:
                self._log(f"✓ {count} imágenes agregadas")
            else:
                messagebox.showinfo("Info", "No se encontraron imágenes")
    
    def _add_image(self, filepath):
        if filepath in self.imagenes:
            return
        
        try:
            img = Image.open(filepath)
            width, height = img.size
            img.close()
            
            self.imagenes.append(filepath)
            
            nombre = os.path.basename(filepath)
            nro = len(self.imagenes)  # ya fue appended
            self.tree_images.insert('', tk.END,
                                   values=(nro, nombre, f"{width}x{height}", "Global", filepath))
            
            # Config con valores globales
            self.configuraciones[filepath] = {
                'tile_size_x': self.tile_size_x_global.get(),
                'tile_size_y': self.tile_size_y_global.get(),
                'overlap': self.overlap_global.get(),
                'puntos': None,
                'polygon': None,
                'angulo_manual': None,
                'skip_last_tile': False
            }
            
            num_recortes = self._calcular_num_recortes(filepath)
            nro_config = len(self.imagenes)
            self.tree_config.insert('', tk.END,
                                   values=(nro_config, nombre,
                                          self.tile_size_x_global.get(),
                                          self.tile_size_y_global.get(),
                                          self.overlap_global.get(),
                                          num_recortes))
            
            nro_poly = len(self.tree_polygons.get_children()) + 1
            self.tree_polygons.insert('', tk.END,
                                     values=(nro_poly, nombre, "No definido", "—"))
            
            if self.output_dir.get():
                self.btn_process.config(state=tk.NORMAL)
                self.btn_process_single.config(state=tk.NORMAL)
            
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar {filepath}\n{str(e)}")
    
    def _on_drop(self, event):
        files = self.root.tk.splitlist(event.data)
        for file in files:
            file = file.strip('{}')
            
            if os.path.isfile(file):
                self._add_image(file)
            elif os.path.isdir(file):
                extensions = ['.tif', '.tiff', '.jpg', '.jpeg', '.png', '.bmp']
                folder_path = Path(file)
                for ext in extensions:
                    for img_file in folder_path.glob(f'*{ext}'):
                        self._add_image(str(img_file))
    
    def _on_preview1_resize(self, event=None):
        """Re-renderiza la vista previa al redimensionar el panel"""
        if self._preview1_filepath:
            self._render_preview1(self._preview1_filepath)

    def _on_image_tree_select(self, event=None):
        """Muestra vista previa de la imagen seleccionada en tab 1"""
        selection = self.tree_images.selection()
        if not selection:
            return

        item_vals = self.tree_images.item(selection[0])['values']
        nombre = item_vals[1]

        filepath = None
        for fp in self.imagenes:
            if os.path.basename(fp) == nombre:
                filepath = fp
                break

        if not filepath:
            return

        self._preview1_filepath = filepath
        self._render_preview1(filepath)

    def _render_preview1(self, filepath):
        """Renderiza la imagen ajustada al tamaño actual del canvas"""
        try:
            nombre = os.path.basename(filepath)
            img = Image.open(filepath)
            w_orig, h_orig = img.size

            self.img_preview_canvas.update_idletasks()
            cw = self.img_preview_canvas.winfo_width()
            ch = self.img_preview_canvas.winfo_height()
            if cw <= 1:
                cw = 300
            if ch <= 1:
                ch = 300

            scale = min(cw / w_orig, ch / h_orig)
            new_w = max(1, int(w_orig * scale))
            new_h = max(1, int(h_orig * scale))

            img_resized = img.resize((new_w, new_h), Image.LANCZOS)
            self.img_preview_photo = ImageTk.PhotoImage(img_resized)
            img.close()

            self.img_preview_canvas.delete("all")
            x_off = (cw - new_w) // 2
            y_off = (ch - new_h) // 2
            self.img_preview_canvas.create_image(x_off, y_off, anchor=tk.NW, image=self.img_preview_photo)

            self.img_preview_info.config(text=f"{nombre}  |  {w_orig} x {h_orig} px")
        except Exception as e:
            self.img_preview_canvas.delete("all")
            self.img_preview_info.config(text=f"Error: {e}")

    def _remove_selected_image(self):
        """Elimina la imagen seleccionada de la lista"""
        selection = self.tree_images.selection()
        if not selection:
            messagebox.showinfo("Info", "Selecciona una imagen para borrar")
            return

        item_vals = self.tree_images.item(selection[0])['values']
        nombre = item_vals[1]  # columna 1 es Nombre (0 es #)

        # Buscar filepath
        filepath = None
        for fp in self.imagenes:
            if os.path.basename(fp) == nombre:
                filepath = fp
                break

        if not filepath:
            return

        # Eliminar de la lista y configuraciones
        self.imagenes.remove(filepath)
        if filepath in self.configuraciones:
            del self.configuraciones[filepath]

        # Eliminar del tree de imágenes
        self.tree_images.delete(selection[0])

        # Re-numerar las filas
        for idx, item_id in enumerate(self.tree_images.get_children(), 1):
            vals = list(self.tree_images.item(item_id)['values'])
            vals[0] = idx
            self.tree_images.item(item_id, values=vals)

        # Eliminar del tree de config y re-numerar
        for item_id in self.tree_config.get_children():
            if self.tree_config.item(item_id)['values'][1] == nombre:
                self.tree_config.delete(item_id)
                break

        for idx, item_id in enumerate(self.tree_config.get_children(), 1):
            vals = list(self.tree_config.item(item_id)['values'])
            vals[0] = idx
            self.tree_config.item(item_id, values=vals)

        # Eliminar del tree de polígonos
        for item_id in self.tree_polygons.get_children():
            if self.tree_polygons.item(item_id)['values'][1] == nombre:
                self.tree_polygons.delete(item_id)
                break

        # Re-numerar tree_polygons
        for idx, item_id in enumerate(self.tree_polygons.get_children(), 1):
            vals = list(self.tree_polygons.item(item_id)['values'])
            vals[0] = idx
            self.tree_polygons.item(item_id, values=vals)

        # Limpiar preview si era la imagen actual
        if filepath == self.current_preview_filepath:
            self.current_preview_filepath = None
            self.current_preview_image = None
            self._clear_polygon_preview()

        if not self.imagenes:
            self.btn_process.config(state=tk.DISABLED)
            self.btn_process_single.config(state=tk.DISABLED)

        self._log(f"Imagen eliminada: {nombre}")

    def _clear_images(self):
        if self.imagenes and messagebox.askyesno("Confirmar", "¿Limpiar todas las imágenes?"):
            self.imagenes = []
            self.configuraciones = {}
            
            for item in self.tree_images.get_children():
                self.tree_images.delete(item)
            
            for item in self.tree_config.get_children():
                self.tree_config.delete(item)
            
            for item in self.tree_polygons.get_children():
                self.tree_polygons.delete(item)
            
            self.btn_process.config(state=tk.DISABLED)
            self.btn_process_single.config(state=tk.DISABLED)
            self._log("Imágenes limpiadas")
    
    def _select_output_dir(self):
        folder = filedialog.askdirectory(title="Directorio de Salida")
        if folder:
            self.output_dir.set(folder)
            if self.imagenes:
                self.btn_process.config(state=tk.NORMAL)
                self.btn_process_single.config(state=tk.NORMAL)
            self._log(f"Directorio: {folder}")
    
    def _define_polygon(self):
        selection = self.tree_polygons.selection()
        if not selection:
            messagebox.showinfo("Info", "Selecciona una imagen")
            return
        
        item = self.tree_polygons.item(selection[0])
        nro = item['values'][0]
        nombre_imagen = item['values'][1]

        filepath = None
        for fp in self.imagenes:
            if os.path.basename(fp) == nombre_imagen:
                filepath = fp
                break

        if not filepath:
            return

        existing = self.configuraciones[filepath].get('polygon')
        selector = PolygonSelectorWindow(self.root, filepath, nombre_imagen, existing)
        polygon = selector.get_result()

        if polygon:
            self.configuraciones[filepath]['polygon'] = polygon

            rot_status = self.tree_polygons.item(selection[0])['values'][3]
            self.tree_polygons.item(selection[0],
                                   values=(nro, nombre_imagen, f"✓ {len(polygon)} pts", rot_status))
            
            self._log(f"Polígono: {nombre_imagen} ({len(polygon)} pts)")
            
            self.current_preview_filepath = filepath
            self._reset_zoom()
            self._update_preview()
            self._update_thumbnail(filepath)
            angulo_guardado = self.configuraciones[filepath].get('angulo_manual')
            self._set_save_rotation_button_state(enabled=True, angle=angulo_guardado)

    def _on_polygon_select(self, event):
        selection = self.tree_polygons.selection()
        if not selection:
            return
        
        item = self.tree_polygons.item(selection[0])
        nombre_imagen = item['values'][1]

        filepath = None
        for fp in self.imagenes:
            if os.path.basename(fp) == nombre_imagen:
                filepath = fp
                break

        if filepath:
            self.current_preview_filepath = filepath

            angulo_guardado = self.configuraciones[filepath].get('angulo_manual')
            if angulo_guardado is not None:
                self.manual_angle.set(angulo_guardado)
            else:
                self.manual_angle.set(0.0)

            self.angle_label.config(text=f"{self.manual_angle.get():.2f}°")

            # Cargar skip_last_tile de esta imagen
            self.skip_last_tile.set(self.configuraciones[filepath].get('skip_last_tile', False))

            self._reset_zoom()
            self._update_preview()
            self._update_thumbnail(filepath)
            self._set_save_rotation_button_state(enabled=True, angle=angulo_guardado)
        else:
            self._clear_polygon_preview()
    
    def _clear_polygon_preview(self):
        try:
            canvas_width = self.preview_canvas.winfo_width()
            canvas_height = self.preview_canvas.winfo_height()
            
            if canvas_width <= 1:
                canvas_width = 500
                canvas_height = 450
            
            self.preview_canvas.delete("all")
            self.preview_canvas.create_rectangle(0, 0, canvas_width, canvas_height,
                                                fill=self.colors['canvas'], outline='')
            self.preview_canvas.create_text(
                canvas_width // 2, canvas_height // 2,
                text="Selecciona una imagen\n\n🎯 Tiles X/Y • Spinbox preciso\n🔍 Zoom • ⚡ Solapamiento visual",
                fill=self.colors['canvas_text'],
                font=(UI_FONT_FAMILY, 11),
                justify=tk.CENTER
            )
            self.preview_info_label.config(text="")
            self.pixel_info_label.config(text="")
            self._set_save_rotation_button_state(enabled=False)
            self.current_preview_image = None
            self._clear_thumbnail()
        except:
            pass
    
    def _use_full_area_all(self):
        if not self.imagenes:
            messagebox.showinfo("Info", "No hay imágenes")
            return
        
        for filepath in self.imagenes:
            try:
                img = Image.open(filepath)
                w, h = img.size
                img.close()
                
                self.configuraciones[filepath]['polygon'] = [(0, 0), (w, 0), (w, h), (0, h)]
            except:
                pass
        
        self.tree_polygons.delete(*self.tree_polygons.get_children())
        for idx, filepath in enumerate(self.imagenes, 1):
            nombre = os.path.basename(filepath)
            poly = self.configuraciones[filepath].get('polygon')
            ang = self.configuraciones[filepath].get('angulo_manual')
            rot_txt = f"✓ {ang:.1f}°" if ang else "—"
            if poly:
                self.tree_polygons.insert('', tk.END,
                                         values=(idx, nombre, "✓ Completa", rot_txt))

        self._log("Área completa → Todas")
    
    def _clear_polygons(self):
        if messagebox.askyesno("Confirmar", "¿Limpiar polígonos?"):
            for filepath in self.imagenes:
                self.configuraciones[filepath]['polygon'] = None
            
            self.tree_polygons.delete(*self.tree_polygons.get_children())
            for idx, filepath in enumerate(self.imagenes, 1):
                nombre = os.path.basename(filepath)
                ang = self.configuraciones[filepath].get('angulo_manual')
                rot_txt = f"✓ {ang:.1f}°" if ang else "—"
                self.tree_polygons.insert('', tk.END,
                                         values=(idx, nombre, "No definido", rot_txt))
            
            self._log("Polígonos limpiados")
    
    # ==================== Procesamiento ====================

    def _start_processing_single(self):
        """Exporta solo la imagen seleccionada actualmente en la vista previa"""
        if not self.current_preview_filepath:
            messagebox.showinfo("Info", "Selecciona una imagen en '2. Vista Previa' primero")
            return

        if not self.output_dir.get():
            messagebox.showwarning("Advertencia", "Selecciona directorio de salida")
            return

        filepath = self.current_preview_filepath
        nombre = os.path.basename(filepath)
        config = self.configuraciones[filepath]

        if config.get('angulo_manual') is None:
            messagebox.showinfo("Info", f"Guarda la rotación de '{nombre}' primero (💾 Guardar Rotación)")
            return

        msg = f"Se exportará solo: {nombre}\n"
        msg += f"Tiles: {config['tile_size_x']}x{config['tile_size_y']}px\n"
        msg += f"¿Continuar?"

        if not messagebox.askyesno("Exportar imagen", msg):
            return

        self.processing = True
        self.should_stop = False
        self.btn_process.config(state=tk.DISABLED)
        self.btn_process_single.config(state=tk.DISABLED)
        self.status_text.delete(1.0, tk.END)
        self.progress_var.set(0)

        config['puntos'] = [(0, 0), (0, 1)]

        def run_single():
            try:
                self._log("="*60)
                self._log(f"EXPORTANDO: {nombre}")
                self._log("="*60)

                def update_progress(msg_text, prog=None):
                    self._log(f"  {msg_text}")
                    if prog is not None:
                        self.progress_var.set(prog)

                tiles = RoadImageProcessor.procesar_imagen(
                    filepath,
                    self.output_dir.get(),
                    config['puntos'],
                    config['tile_size_x'],
                    config['tile_size_y'],
                    config['overlap'],
                    config.get('polygon') if self.use_polygon.get() else None,
                    config.get('angulo_manual'),
                    self.use_gpu.get(),
                    False,
                    update_progress,
                    self.export_format.get(),
                    self.carpeta_por_imagen.get()
                )

                self.progress_var.set(100)
                self._log(f"\n✓ Completado: {tiles} tiles exportados")
                self.root.after(0, lambda: messagebox.showinfo("Completado",
                    f"✓ {nombre}\n{tiles} tiles exportados"))

            except Exception as e:
                self._log(f"\n❌ ERROR: {str(e)}")
                self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                self.processing = False
                self.should_stop = False
                self.root.after(0, lambda: [self.btn_process.config(state=tk.NORMAL),
                                           self.btn_process_single.config(state=tk.NORMAL)])

        thread = threading.Thread(target=run_single)
        thread.daemon = True
        thread.start()

    def _start_processing(self):
        if not self.imagenes:
            messagebox.showwarning("Advertencia", "No hay imágenes")
            return
        
        if not self.output_dir.get():
            messagebox.showwarning("Advertencia", "Selecciona directorio de salida")
            return
        
        manual_count = sum(1 for fp in self.imagenes 
                          if self.configuraciones[fp].get('angulo_manual') is not None)
        
        msg = f"Se procesarán {len(self.imagenes)} imágenes.\n\n"
        msg += f"✨ Tiles rectangulares (X/Y)\n"
        msg += f"✨ Recorte completo SIN RESTOS\n"
        if manual_count > 0:
            msg += f"🎯 {manual_count} con rotación MANUAL\n"
        if self.use_polygon.get():
            msg += "🔷 Polígonos activos\n"
        msg += "\n¿Continuar?"
        
        if not messagebox.askyesno("Confirmar", msg):
            return
        
        self.processing = True
        self.should_stop = False
        
        self.btn_process.config(state=tk.DISABLED)
        self.btn_process_single.config(state=tk.DISABLED)
        self.status_text.delete(1.0, tk.END)
        self.progress_var.set(0)
        
        thread = threading.Thread(target=self._process_images)
        thread.daemon = True
        thread.start()
    
    def _process_images(self):
        try:
            # FASE 1: Ejes
            self._log("="*60)
            self._log("FASE 1: SELECCIÓN DE EJES")
            self._log("="*60)
            
            for i, filepath in enumerate(self.imagenes, 1):
                if self.should_stop:
                    self._log("\n❌ Cancelado")
                    return
                
                nombre = os.path.basename(filepath)
                
                if self.configuraciones[filepath].get('angulo_manual') is not None:
                    self._log(f"\n[{i}/{len(self.imagenes)}] {nombre}: Rotación manual ✓")
                    self.configuraciones[filepath]['puntos'] = [(0, 0), (0, 1)]
                    continue
                
                self._log(f"\n[{i}/{len(self.imagenes)}] Selecciona eje: {nombre}")
                
                puntos = None
                
                def open_selector():
                    nonlocal puntos
                    selector = ImageSelectorWindow(self.root, filepath, nombre)
                    puntos = selector.get_result()
                
                self.root.after(0, open_selector)
                
                while puntos is None and self.root.winfo_exists() and not self.should_stop:
                    self.root.update()
                    if filepath not in self.configuraciones:
                        break
                
                if self.should_stop:
                    return
                
                if puntos is None:
                    self._log(f"✗ Omitida: {nombre}")
                    continue
                
                self.configuraciones[filepath]['puntos'] = puntos
                self._log(f"✓ Puntos: {puntos}")
            
            if self.should_stop:
                return
            
            imagenes_a_procesar = [fp for fp in self.imagenes 
                                  if self.configuraciones[fp]['puntos'] is not None]
            
            if not imagenes_a_procesar:
                self._log("\n❌ No hay imágenes")
                return
            
            # FASE 2: Procesamiento
            self._log("\n" + "="*60)
            self._log("FASE 2: PROCESAMIENTO")
            self._log("="*60)
            self._log(f"Imágenes: {len(imagenes_a_procesar)}\n")
            
            total_tiles = 0
            total_time_start = time.time()
            
            for i, filepath in enumerate(imagenes_a_procesar, 1):
                if self.should_stop:
                    return
                
                config = self.configuraciones[filepath]
                nombre = os.path.basename(filepath)
                
                self._log(f"\n[{i}/{len(imagenes_a_procesar)}] {nombre}")
                self._log(f"  Config: {config['tile_size_x']}x{config['tile_size_y']}px, overlap={config['overlap']}px")
                
                def update_progress(msg, prog=None):
                    self._log(f"  {msg}")
                    if prog is not None:
                        self.progress_var.set(prog)
                
                tiles = RoadImageProcessor.procesar_imagen(
                    filepath,
                    self.output_dir.get(),
                    config['puntos'],
                    config['tile_size_x'],
                    config['tile_size_y'],
                    config['overlap'],
                    config.get('polygon') if self.use_polygon.get() else None,
                    config.get('angulo_manual'),
                    self.use_gpu.get(),
                    False,
                    update_progress,
                    self.export_format.get(),
                    self.carpeta_por_imagen.get()
                )

                total_tiles += tiles

                progreso = (i / len(imagenes_a_procesar)) * 100
                self.progress_var.set(progreso)
            
            total_time = time.time() - total_time_start
            
            self._log("\n" + "="*60)
            self._log("✓ COMPLETADO")
            self._log("="*60)
            self._log(f"Imágenes: {len(imagenes_a_procesar)}")
            self._log(f"Tiles: {total_tiles}")
            self._log(f"Tiempo: {total_time:.1f}s")
            self._log(f"Ubicación: {self.output_dir.get()}")
            self._log("="*60)
            
            summary = f"✓ {len(imagenes_a_procesar)} imágenes | {total_tiles} tiles | {total_time:.1f}s"
            self.root.after(0, lambda: self.summary_label.config(text=summary))
            
            self.root.after(0, lambda: messagebox.showinfo("Completado", 
                                                          f"✓ Procesamiento completado\n\n"
                                                          f"Imágenes: {len(imagenes_a_procesar)}\n"
                                                          f"Tiles: {total_tiles}\n"
                                                          f"Tiempo: {total_time:.1f}s"))
            
        except Exception as e:
            self._log(f"\n❌ ERROR: {str(e)}")
            import traceback
            self._log(traceback.format_exc())
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
        
        finally:
            self.processing = False
            self.should_stop = False
            self.root.after(0, lambda: [self.btn_process.config(state=tk.NORMAL),
                                       self.btn_process_single.config(state=tk.NORMAL)])
    
    def _log(self, message):
        def add_text():
            self.status_text.insert(tk.END, message + "\n")
            self.status_text.see(tk.END)
        
        self.root.after(0, add_text)
    
    def _save_config(self):
        config = {
            'output_dir': self.output_dir.get(),
            'tile_size_x_global': self.tile_size_x_global.get(),
            'tile_size_y_global': self.tile_size_y_global.get(),
            'overlap_global': self.overlap_global.get(),
            'use_polygon': self.use_polygon.get(),
            'use_gpu': self.use_gpu.get(),
            'join_input_dir': self.join_input_dir.get(),
            'join_output_dir': self.join_output_dir.get(),
            'join_columns': self.join_columns.get(),
            'join_spacing': self.join_spacing.get(),
            'join_start_index': self.join_start_index.get(),
            'join_end_index': self.join_end_index.get(),
            'join_batch_size': self.join_batch_size.get(),
            'join_include_subfolders': self.join_include_subfolders.get(),
            'join_group_keyword': self.join_group_keyword.get()
        }
        
        try:
            with open('road_processor_config.json', 'w') as f:
                json.dump(config, f)
        except:
            pass
    
    def _load_config(self):
        try:
            if os.path.exists('road_processor_config.json'):
                with open('road_processor_config.json', 'r') as f:
                    config = json.load(f)

                self._suppressing_trace = True
                self.output_dir.set(config.get('output_dir', ''))
                self.tile_size_x_global.set(config.get('tile_size_x_global', 820))
                self.tile_size_y_global.set(config.get('tile_size_y_global', 820))
                self.overlap_global.set(config.get('overlap_global', 5))
                self.use_polygon.set(config.get('use_polygon', False))
                self.use_gpu.set(config.get('use_gpu', GPU_AVAILABLE))
                self.join_input_dir.set(config.get('join_input_dir', ''))
                self.join_output_dir.set(config.get('join_output_dir', ''))
                self.join_columns.set(config.get('join_columns', 0))
                self.join_spacing.set(config.get('join_spacing', 0))
                self.join_start_index.set(config.get('join_start_index', 0))
                self.join_end_index.set(config.get('join_end_index', -1))
                self.join_batch_size.set(config.get('join_batch_size', 0))
                self.join_include_subfolders.set(config.get('join_include_subfolders', True))
                self.join_group_keyword.set(config.get('join_group_keyword', ''))
                self._suppressing_trace = False
        except:
            self._suppressing_trace = False
    
    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self._force_quit()
    
    def _on_closing(self):
        try:
            if self.processing:
                if not messagebox.askyesno("Procesamiento en curso", 
                                          "¿Detener y salir?"):
                    return
                
                self.should_stop = True
            
            self._save_config()
            self.root.quit()
            self.root.destroy()
            
            import sys
            sys.exit(0)
            
        except:
            self._force_quit()
    
    def _force_quit(self):
        import os
        try:
            self.root.destroy()
        except:
            pass
        os._exit(0)


def main():
    print("="*70)
    print("🛣️  PROCESADOR PRO - VERSIÓN COMPLETA")
    print("="*70)
    print("\n✨ CARACTERÍSTICAS:")
    print("  🎯 Ajuste de precisión con spinbox (±0.1°)")
    print("  📊 Tiles rectangulares (ancho X y alto Y separados)")
    print("  🔍 Zoom en ventana de polígonos")
    print("  ⚡ Visualización de solapamiento entre tiles")
    print("  ✂️ Recorte COMPLETO sin dejar restos en bordes")
    print("  📐 Vista previa reorganizada (arriba)")
    print("  💡 Información de píxeles en tiempo real")
    print("\nIniciando...")
    
    try:
        import cv2
        import numpy
        from PIL import Image
        print("✓ Dependencias OK")
    except ImportError as e:
        print(f"❌ Error: {e}")
        print("\nInstalar: pip install pillow numpy opencv-python")
        input("\nEnter para salir...")
        return
    
    if GPU_AVAILABLE:
        print(f"\n✓ GPU CUDA")
    else:
        print(f"\n⚠ CPU ({CPU_CORES} cores)")
    
    print("\n" + "="*70 + "\n")
    
    app = RoadProcessorGUI()
    app.run()


if __name__ == "__main__":
    main()


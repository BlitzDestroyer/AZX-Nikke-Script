from __future__ import annotations

import ctypes
import threading
from typing import TypeAlias, cast

import keyboard
import mss
import numpy as np
import cv2
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QApplication

RGBA: TypeAlias = tuple[int, int, int, int]
Matrix: TypeAlias = list[list[int | str]]

RED_CHAR = "\u25A1"
RED_COLOR: RGBA = (255, 0, 0, 200)
RED_PASTEL_CHAR = "\u25A0"
RED_PASTEL_COLOR: RGBA = (255, 0, 0, 70)
GREEN_CHAR = "\u25BA"
GREEN_COLOR: RGBA = (0, 255, 0, 200)
GREEN_PASTEL_CHAR = "\u2192"
GREEN_PASTEL_COLOR: RGBA = (0, 255, 0, 70)
BLUE_CHAR = "\u25BC"
BLUE_COLOR: RGBA = (0, 0, 255, 200)
BLUE_PASTEL_CHAR = "\u2193"
BLUE_PASTEL_COLOR: RGBA = (0, 0, 255, 70)
BLACK_COLOR: RGBA = (0, 0, 0, 0)

MAX_SUMMABLE_VALUE = 10

CHAR_COLOR_MAP: dict[str, RGBA] = {
    RED_CHAR: RED_COLOR,
    RED_PASTEL_CHAR: RED_PASTEL_COLOR,
    GREEN_CHAR: GREEN_COLOR,
    GREEN_PASTEL_CHAR: GREEN_PASTEL_COLOR,
    BLUE_CHAR: BLUE_COLOR,
    BLUE_PASTEL_CHAR: BLUE_PASTEL_COLOR
}

class Overlay(QtWidgets.QWidget):

    def __init__(self, rows, cols, left_start, top_start, offset_x, offset_y, w, h):
        super().__init__()

        self.rows = rows
        self.cols = cols

        self.left_start = left_start
        self.top_start = top_start
        self.offset_x = offset_x
        self.offset_y = offset_y

        self.cell_w = w
        self.cell_h = h

        self.cells = []

        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        self.setGeometry(0, 0, 1920, 1080)

        self.show()

        #Click-through
        hwnd = self.winId().__int__()
        ctypes.windll.user32.SetWindowLongW(
            hwnd, -20,
            ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            | 0x80000  #WS_EX_LAYERED
            | 0x20     #WS_EX_TRANSPARENT
        )

    def setCells(self, cell_list):
        self.cells = cell_list
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)

        for (r, c, color) in self.cells:
            r_px = self.top_start + r * self.offset_y
            c_px = self.left_start + c * self.offset_x

            brush = QtGui.QColor(*color)
            painter.setBrush(brush)
            painter.setPen(QtGui.QPen(QtGui.QColor(255,255,255,180), 2))

            painter.drawRect(c_px, r_px, self.cell_w, self.cell_h)

#rows and columns from the level

rows = 16; columns = 10

#pixels

offset_x = 51; offset_y = 52
top_start = 221; left_start = 708 
capture_area_w = 44; capture_area_h = 45

numbers: list[int | str] = []
matrix: Matrix = []

start_area = {
    "top": top_start,
    "left": left_start,
    "width": capture_area_w,
    "height": capture_area_h
}

def getMatrixNumbers():
    counter = 0

    with mss.mss() as sct:
        for _ in range(rows):
            for _ in range(columns):
                counter += 1

                image = sct.grab(start_area)

                img_np = np.array(image)
                img_gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)

                img_np = np.array(image)

                best_score = -10 
                best_match_digit = -1

                for j in range(1, 10):
                    template_path = f"./templates/T{j}.png"
                    template = cv2.imread(template_path)

                    if template is None:
                        print(f"Couldn't load template: {template_path}")
                        continue

                    temp_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

                    res = cv2.matchTemplate(img_gray, temp_gray, cv2.TM_CCOEFF_NORMED)
                    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

                    current_score = max_val

                    if current_score > best_score:
                        best_score = current_score
                        best_match_digit = j
                
                if best_match_digit != -1:
                    numbers.append(best_match_digit)
                else:
                    print("Not valid match, replacing with whitespace.")
                    numbers.append(" ")

                start_area["left"] += offset_x

            start_area["left"] = left_start
            start_area["top"] += offset_y

    createMatrix()

def createMatrix():
    pos = 0

    for _ in range(rows):
        row: list[int | str] = []
        for _ in range(columns):
            row.append(numbers[pos])
            pos += 1
        matrix.append(row)

    printMatrix()

def printMatrix():
    print("Matrix: ")

    for i in range(rows):
        for j in range(columns):
            print(matrix[i][j], end="  ")
        print()

def checkRight(columns: int, r: int, c: int, matrix: Matrix) -> tuple[bool, int]:
    sum = 0
    for j in range(columns - c):

        if c + j > columns:
            return False, 0

        if (hasSpecialChar(r, c + j)):
            continue
        else:
            # Safety: hasSpecialChar will filter out non-integer values
            sum += cast(int, matrix[r][c + j])

        if sum > MAX_SUMMABLE_VALUE:
            return False, 0
        elif sum == MAX_SUMMABLE_VALUE:
            return True, j
        
    return False, 0

def sumsRight():
    for r in range(rows):
        for c in range(columns):
            if hasSpecialChar(r,c):
                continue

            validSum, positions = checkRight(columns, r, c, matrix)

            if validSum:
                for x in range(1, positions + 1):
                    matrix[r][c + x] = GREEN_PASTEL_CHAR
                matrix[r][c] = GREEN_CHAR

    printMatrix()
    updateOverlay()

def checkDown(rows: int, r: int, c: int, matrix: Matrix) -> tuple[bool, int]:
    sum = 0

    for j in range(rows - r):
        if r + j > rows:
            return False, 0

        if hasSpecialChar(r + j, c):
            continue
        else:
            # Safety: hasSpecialChar will filter out non-integer values
            sum += cast(int, matrix[r + j][c])

        if sum > MAX_SUMMABLE_VALUE:
            return False, 0
        elif sum == MAX_SUMMABLE_VALUE:
            return True, j
        
    return False, 0

def sumsDown():
    positions = 0
    for c in range(columns):
        for r in range(rows):
            if hasSpecialChar(r,c):
                continue

            validSum, positions = checkDown(rows, r, c, matrix)

            if validSum:
                for x in range(1, positions + 1):
                    matrix[x + r][c] = BLUE_PASTEL_CHAR
                matrix[r][c] = BLUE_CHAR
    
    printMatrix()
    updateOverlay()

def checkSquareUp(rows: int, columns: int, start_r: int, start_c: int, matrix: Matrix) -> tuple[bool, int, int]:
    if start_r <= 0 or start_c >= columns:
        return False, 0, 0

    if hasSpecialChar(start_r, start_c):
        return False, 0, 0

    edge_rows = start_r - 1 
    edge_columns = start_c + 1
    area = 1

    while edge_rows >= 0 and edge_columns < columns:
        sum = 0

        for r in range(edge_rows, start_r + 1):
            for c in range(start_c, edge_columns + 1):
                if not hasSpecialChar(r, c):
                    sum += int(matrix[r][c])

        if sum > MAX_SUMMABLE_VALUE:
            return False, 0, 0

        if sum == MAX_SUMMABLE_VALUE:
            return True, edge_rows, edge_columns

        if edge_columns >= columns or edge_rows < 0:
             return False, 0, 0

        current_col = edge_columns
        sum_col = sum

        while current_col + 1 < columns:
            current_col += 1

            for r in range(edge_rows, start_r + 1):
                if not hasSpecialChar(r, current_col):
                    sum_col += int(matrix[r][current_col])

            if sum_col > MAX_SUMMABLE_VALUE:
                break

            if sum_col == MAX_SUMMABLE_VALUE:
                return True, edge_rows, current_col

        current_row = edge_rows
        sum_row = sum

        while current_row - 1 >= 0:
            current_row -= 1

            for c in range(start_c, edge_columns + 1):
                if not hasSpecialChar(current_row, c):
                    sum_row += int(matrix[current_row][c])

            if sum_row > MAX_SUMMABLE_VALUE:
                break

            if sum_row == MAX_SUMMABLE_VALUE:
                return True, current_row, edge_columns

        edge_rows -= 1
        edge_columns += 1
        area += 1

    return False, 0, 0

def checkSquareDown(rows: int, columns: int, start_r: int, start_c: int, matrix: Matrix) -> tuple[bool, int, int]:
    if start_r >= rows or start_c >= columns:
        return False, 0, 0

    if hasSpecialChar(start_r, start_c):
        return False, 0, 0

    edge_rows = start_r + 1; edge_columns = start_c + 1
    area = 1

    while edge_rows < rows and edge_columns < columns:
        sum = 0

        for r in range(start_r, edge_rows + 1):
            for c in range(start_c, edge_columns + 1):
                if not hasSpecialChar(r, c):
                    sum += int(matrix[r][c])

        if sum > MAX_SUMMABLE_VALUE:
            return False, 0, 0

        if sum == MAX_SUMMABLE_VALUE:
            return True, edge_rows, edge_columns


        if edge_columns > columns or edge_rows > rows:
            return False, 0, 0

        current_col = edge_columns
        sum_col = sum

        while current_col + 1 < columns:
            current_col += 1

            for r in range(start_r, edge_rows + 1):
                if not hasSpecialChar(r, current_col):
                    sum_col += int(matrix[r][current_col])

            if sum_col > MAX_SUMMABLE_VALUE:
                break

            if sum_col == MAX_SUMMABLE_VALUE:
                return True, edge_rows, current_col

        current_row = edge_rows
        sum_row = sum

        while current_row + 1 < rows:
            current_row += 1

            for c in range(start_c, edge_columns + 1):
                if not hasSpecialChar(current_row, c):
                    sum_row += int(matrix[current_row][c])

            if sum_row > MAX_SUMMABLE_VALUE:
                break

            if sum_row == MAX_SUMMABLE_VALUE:
                return True, current_row, edge_columns

        edge_rows += 1
        edge_columns += 1
        area += 1

    return False, 0, 0

def sumsSquare():
    for r in range(rows):
        for c in range(columns):
            if hasSpecialChar(r, c):
                continue
            
            validSumDown, max_r, max_c = checkSquareDown(rows, columns, r, c, matrix)
            if validSumDown:
                for j in range(r, max_r + 1):
                    for k in range(c, max_c + 1):
                        matrix[j][k] = RED_PASTEL_CHAR
                matrix[r][c] = RED_CHAR
                continue
            
            validSumUp, max_r, max_c = checkSquareUp(rows, columns, r, c, matrix)
            if validSumUp:
                for j in range(r, max_r - 1, -1):
                    for k in range(c, max_c + 1):
                        matrix[j][k] = RED_PASTEL_CHAR
                matrix[r][c] = RED_CHAR

    printMatrix()
    updateOverlay()

def hasSpecialChar(r: int, c: int) -> bool:
    return matrix[r][c] in (RED_CHAR, RED_PASTEL_CHAR, GREEN_CHAR, GREEN_PASTEL_CHAR, BLUE_CHAR, BLUE_PASTEL_CHAR, " ")
    # if matrix[r][c] == "\u2192" or matrix[r][c] == "\u2193" or matrix[r][c] == "\u25A0" or matrix[r][c] == "\u25A1" or matrix[r][c] == "\u25BA" or matrix[r][c] == "\u25BC" or matrix[r][c] == " ":
    #     return True
    # return False

def cleanSpecialCharactersFromMatrix():
    for r in range(rows):
        for c in range(columns):
            if hasSpecialChar(r, c):
                matrix[r][c] = " "
            else:
                continue

    print("Cleaned special characters from matrix: ")
    printMatrix()
    updateOverlay()

def updateOverlay():
    cell_list: list[tuple[int, int, RGBA]] = []

    for r in range(rows):
        for c in range(columns):
            value = matrix[r][c]

            if isinstance(value, int):
                continue

            color = CHAR_COLOR_MAP.get(value, BLACK_COLOR)
            cell_list.append((r, c, color))
            # if value == "\u25A0":
            #     cell_list.append((r, c, (255, 0, 0, 70)))
            # elif value == "\u25A1":
            #     cell_list.append((r, c, (255, 0, 0, 200)))
            # elif value =="\u2192":
            #     cell_list.append((r, c, (0, 255, 0, 70)))
            # elif value =="\u2193":
            #     cell_list.append((r, c, (0, 0, 255, 70)))
            # elif value =="\u25BA":
            #     cell_list.append((r, c, (0, 255, 0, 200)))
            # elif value =="\u25BC":
            #     cell_list.append((r, c, (0, 0, 255, 200)))
            # elif value ==" ":
            #     cell_list.append((r, c, (0, 0, 0, 0)))

    overlay.setCells(cell_list)


def configureHotkeys():
    print("f1. clean matrix")
    print("f2. sums right")
    print("f3. sums down")
    print("f4. sums square")
    print("f5. scan matrix")

    keyboard.add_hotkey('f5', getMatrixNumbers)
    keyboard.add_hotkey('f3', sumsDown)
    keyboard.add_hotkey('f2', sumsRight)
    keyboard.add_hotkey('f4', sumsSquare)
    keyboard.add_hotkey('f1', cleanSpecialCharactersFromMatrix)

    keyboard.add_hotkey("esc", lambda: QtWidgets.QApplication.quit())
    
    keyboard.wait()

if __name__ == "__main__":
    app = QApplication([])

    overlay = Overlay(
        rows, columns,
        left_start, top_start,
        offset_x, offset_y,
        capture_area_w, capture_area_h
    )

    logic_thread = threading.Thread(target=configureHotkeys, daemon=True)
    logic_thread.start()

    app.exec_()
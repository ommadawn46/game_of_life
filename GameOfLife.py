from PIL import Image, ImageTk
import numpy as np
import tkinter
import time
import re

# ライフゲーム
class GameOfLife:
    def __init__(self, row=100, col=100, rle=None, log_length=50, infinite=True):
        if rle:
            self.load_rle(rle)
        else:
            self.F = np.zeros((row, col))
        self.infinite = infinite
        self.log_length = log_length
        self.prev_log = []
        self.next_log = []

    def step(self):
        """次の世代へ進める"""
        self.logging()
        self.next_log = []
        F = self.F
        S = np.zeros(F.shape, dtype=np.int8)
        if self.infinite:
            F[0], F[-1], F[:, :1], F[:, -1:] = F[-2], F[1], F[:, -2:-1], F[:, 1:2]
            F[(0, 0, -1, -1), (0, -1, 0, -1)] = F[(-2, -2, 1, 1), (-2, 1, -2, 1)]
        S[1:-1, 1:-1] = S[1:-1, 1:-1] + F[:-2, :-2] + F[:-2, 1:-1] + F[:-2, 2:] + F[1:-1, :-2] + F[1:-1, 2:] + F[2:, :-2] + F[2:, 1:-1] + F[2:, 2:]
        self.F = ((S == 3) | ((F == 1) & (S == 2)))

    def logging(self):
        """現在のパターンのログを取る"""
        self.prev_log.append(self.F)
        if len(self.prev_log) > self.log_length:
            self.prev_log.pop(0)

    def undo(self):
        """世代を一つ前に戻す"""
        if len(self.prev_log) > 0:
            self.next_log.append(self.F)
            if len(self.next_log) > self.log_length:
                self.next_log.pop(0)
            self.F = self.prev_log.pop()

    def redo(self):
        """undoの取り消し / 次の世代へ進める"""
        if len(self.next_log) > 0:
            self.logging()
            self.F = self.next_log.pop()
        else:
            self.step()

    def switch(self, row, col):
        """セルの生死を反転させる"""
        if 0 <= row and row < self.F.shape[0] and 0 <= col and col < self.F.shape[1]:
            self.F = self.F.copy()
            self.F[row, col] = not self.F[row, col]

    def as_image(self):
        """現在のパターンを画像イメージ化する"""
        g = Image.fromarray(np.uint8(self.F) * 254 + 1)
        rb = Image.new('L', g.size, 1)
        return Image.merge('RGB', (rb, g, rb))

    def load_rle(self, rle):
        """rleファイルからパターンを読み込む"""
        with open(rle, 'r') as f:
            data = f.read().splitlines()
        size_pattern = re.compile(r"x\s*=\s*(\d+),\s*y\s*=\s*(\d+),\s*rule\s*=\s*(.+)")
        for i in range(len(data)):
            line = data[i]
            result = size_pattern.search(line)
            if result:
                col, row = int(result.group(1)), int(result.group(2))
                rule = result.group(3)
                tmp = ''.join(data[i+1:]).split('!')[0]
                tmp = re.sub(r'(\d+)([bo$])', lambda m: int(m.group(1))*m.group(2), tmp)
                gol_pattern = tmp.split('$')
                break
        F = np.zeros((row+100, col+100))
        for r in range(len(gol_pattern)):
            gol_pattern[r] += 'b'*(col - len(gol_pattern[r]))
            for c in range(len(gol_pattern[r])):
                F[r+50, c+50] = gol_pattern[r][c] == 'o'
        self.F = F


# ライフゲーム描画キャンパス
class GOLCanvas(tkinter.Canvas):
    def __init__(self, window, width, height, row=None, col=None, rle=None):
        super(GOLCanvas, self).__init__(window, width=width, height=height)
        self.rle = rle
        self.game_of_life = GameOfLife(rle=rle) if self.rle else GameOfLife(row=row, col=col)
        self.row, self.col = self.game_of_life.F.shape
        self.original_F = self.game_of_life.F.copy()
        self.window = window

        self.window_width, self.window_height = width, height
        self.width = width if self.col < width else self.col
        self.height = height if self.row < height else self.row
        self.scale = max(1.0, min(self.window_width / self.col, self.window_height / self.row))

        self.bx = 0 if self.col < self.window_width else (self.window_width - self.col) / 2
        self.by = 0 if self.row < self.window_height else (self.window_height - self.row) / 2

        self.image = Image.new('RGB', (max(self.width, self.col), max(self.height, self.row)))
        self.ix = int((self.width - self.col) / 2)
        self.iy = int((self.height - self.row) / 2)
        self.photo = None
        self.photo_id = self.create_image(self.width/2, self.height/2)

        self.fps = 20.0
        self.steps_by_frame = 1
        self.running = False

        self.window.bind('<space>', self.on_space_pressed)
        self.window.bind("<Up>", self.on_up_pressed)
        self.window.bind("<Down>", self.on_down_pressed)
        self.window.bind("<Right>", self.on_right_pressed)
        self.window.bind("<Left>", self.on_left_pressed)
        self.window.bind("<Escape>", self.on_esc_pressed)
        self.window.bind("<Key>", self.on_key_pressed)
        self.bind("<ButtonPress-1>", self.on_clicked)
        self.bind("<B1-Motion>", self.on_dragged)
        self.bind("<ButtonPress-2>", self.on_right_clicked)
        self.bind("<B2-Motion>", self.on_right_dragged)
        self.draw()

    def on_space_pressed(self, event):
        """スペース: シミュレーションの停止 / 再開"""
        self.running = not self.running
        if self.running:
            self.window.after(0, self.simulation_loop)

    def on_up_pressed(self, event):
        """UP: 拡大"""
        self.scale *= 1.05
        self.draw()

    def on_down_pressed(self, event):
        """DOWN: 縮小"""
        self.scale *= 1.0 / 1.05
        if self.scale < 0.01:
            self.scale = 0.01
        self.draw()

    def on_right_pressed(self, event):
        """RIGHT: REDO"""
        self.game_of_life.redo()
        self.draw()

    def on_left_pressed(self, event):
        """LEFT: UNDO"""
        self.game_of_life.undo()
        self.draw()

    def on_esc_pressed(self, event):
        """ESC: シミュレーションを初期化する"""
        self.game_of_life.F = self.original_F.copy()

    def on_key_pressed(self, event):
        """Z: FPSを下げる
        X: FPSを上げる
        A: フレームあたりの世代更新数を下げる
        X: フレームあたりの世代更新数を上げる
        I: 端でループするかを切り替え"""
        key = event.char.lower()
        if key == 'z':
            self.fps *= 1.0 / 1.1
        elif key == 'x':
            self.fps *= 1.1
        elif key == 'a':
            self.steps_by_frame -= 1
            if self.steps_by_frame < 1:
                self.steps_by_frame = 1
        elif key == 's':
            self.steps_by_frame += 1
        elif key == 'i':
            self.game_of_life.infinite = not self.game_of_life.infinite

    def on_clicked(self, event):
        """左クリック: セルの生死を反転"""
        ex, ey = event.x, event.y
        bx, by = map(round, (self.bx, self.by))
        self.click_row = int(ey/self.scale - by/2 + int((self.height - self.height/self.scale)/2) - self.iy)
        self.click_col = int(ex/self.scale - bx/2 + int((self.width - self.width/self.scale)/2) - self.ix)
        self.game_of_life.logging()
        self.game_of_life.switch(self.click_row, self.click_col)
        self.draw()

    def on_dragged(self, event):
        """左ドラッグ: セルの生死を反転"""
        ex, ey = event.x, event.y
        bx, by = map(round, (self.bx, self.by))
        drag_row = int(ey/self.scale - by/2 + int((self.height - self.height/self.scale)/2) - self.iy)
        drag_col = int(ex/self.scale - bx/2 + int((self.width - self.width/self.scale)/2) - self.ix)
        if drag_row != self.click_row or drag_col != self.click_col:
            self.click_row = drag_row
            self.click_col = drag_col
            self.game_of_life.switch(drag_row, drag_col)
            self.draw()

    def on_right_clicked(self, event):
        """右クリック - 押したとき: クリック位置の保存"""
        ex, ey = event.x, event.y
        self.sx, self.sy = ex, ey

    def on_right_dragged(self, event):
        """右ドラッグ: 描画領域をずらす"""
        ex, ey = event.x, event.y
        self.bx += (ex - self.sx) / self.scale
        self.by += (ey - self.sy) / self.scale
        self.sx, self.sy = ex, ey
        self.draw()

    def draw(self):
        """描画"""
        x, y = map(round, (self.bx, self.by))
        iw, ih = self.image.size
        self.image = Image.new('RGB', (iw, ih))
        self.image.paste(self.game_of_life.as_image(), (self.ix, self.iy))
        cw, ch = iw / self.scale, ih / self.scale
        nx, ny = int((iw - cw - x) / 2), int((ih - ch - y) / 2)
        tmp = self.image.crop((nx, ny, nx + int(cw), ny + int(ch)))
        tmp = tmp.point(lambda x: 20 if x == 0 else x)
        size = int(cw * self.scale), int(ch * self.scale)
        self.photo = ImageTk.PhotoImage(tmp.resize(size))
        self.itemconfig(self.photo_id, image=self.photo)

    def simulation_loop(self):
        """メインループ"""
        err = 0
        prev_time = time.time()
        while self.running:
            for _ in [0]*self.steps_by_frame:
                self.game_of_life.step()
            self.draw()
            self.update()
            finish_time = time.time()
            sleep_length = max(0, 1.0/self.fps - (finish_time - prev_time) - err)
            time.sleep(sleep_length)
            prev_time = time.time()
            err = sleep_length - (prev_time - finish_time)


if __name__ == '__main__':
    root = tkinter.Tk()
    root.title('Game of Life')
    width, height = 1300, 700
    col, row = 140, 140
    canvas = GOLCanvas(root, width, height, row=row, col=col)
    # パターンをファイルから読み込む場合は以下のように指定する
    #canvas = GOLCanvas(root, width, height, rle='rle/2c5-spaceship-gun-p416.rle')
    canvas.pack()
    root.mainloop()

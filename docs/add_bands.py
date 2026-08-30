# -*- coding: utf-8 -*-
"""为 originbot 架构图添加分层背景色带 (在 graph0 之前插入根级背景, 不破坏 transform)
用法(在 docs/ 目录下):
  neato -n2 -Tsvg arch.dot -o /tmp/raw.svg
  python3 add_bands.py
"""
import subprocess, sys

RAW = '/tmp/raw.svg'
OUT = '/home/hantao/myCode/Origin_bot/3.0_car/docs/originbot_软件架构图.svg'
DOT = '/home/hantao/myCode/Origin_bot/3.0_car/docs/arch.dot'

subprocess.run(['neato', '-n2', '-Tsvg', DOT, '-o', RAW], check=True)
svg = open(RAW, encoding='utf-8').read()

# 1) graph0 的 translate 偏移(根坐标 -> 图组内部坐标)
import re
m = re.search(r'<g id="graph0" class="graph"([^>]*)>', svg)
g0_start = m.end() - 1          # '>' 的位置
g0_attrs = m.group(1)
tm = re.search(r'translate\(([-\d.]+) ([-\d.]+)\)', g0_attrs)
if not tm:
    print('ERROR: 未找到 graph0 的 translate 属性'); sys.exit(1)
ox, oy = float(tm.group(1)), float(tm.group(2))

# 2) 各层背景带 (基于节点首行文字的视图坐标)
nodes = []
for part in svg.split('<g id="node')[1:]:
    block = part.split('</g>')[0]
    if '<text ' not in block:
        continue
    t = block.split('<text ')[1]
    x = float(t.split('x="')[1].split('"')[0]) + ox
    y = float(t.split('y="')[1].split('"')[0]) + oy
    name = t.split('>')[1].split('<')[0]
    nodes.append((x, y, name))

xmin = min(x for x,_,_ in nodes)
xmax = max(x for x,_,_ in nodes)

def zone(ys): return (min(ys)-13, max(ys)+13)
br  = [y for x,y,n in nodes if y < 110]          # 编排层
app = [y for x,y,n in nodes if 110 <= y < 185]   # 应用层
drv = [y for x,y,n in nodes if 185 <= y < 250]   # 驱动层
hw  = [y for x,y,n in nodes if y >= 250]         # 硬件层

layer_label = ['编 排 层', '应 用 层', '驱 动 层', '硬 件 层']
layer_fill  = ['#FFF9EC', '#F8F0F5', '#F0F8EE', '#FCF4E8']
layer_edge  = ['#D9C08A', '#C9A3C0', '#9FC7A8', '#D9B78E']

left = xmin - 65
width = (xmax + 70) - left
insert = ''
bands = []
for i,(y0,y1) in enumerate([zone(br), zone(app), zone(drv), zone(hw)]):
    h = y1 - y0
    if h <= 0:
        continue
    bands.append((round(y0,1), round(y1,1)))
    insert += ('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" '
               'stroke="%s" stroke-width="1.2" stroke-dasharray="7,4" rx="9"/>\n'
               % (left, y0, width, h, layer_fill[i], layer_edge[i]))
    insert += ('<text x="%.1f" y="%.1f" font-family="Noto Sans CJK SC" font-size="12" '
               'fill="%s" font-weight="bold">%s</text>\n'
               % (left+12, y0+18, layer_edge[i], layer_label[i]))

# 3) 在 graph0 之前插入 (根级背景, 图形组原封不动)
n = svg.find('<g id="graph0"')
if n < 0:
    print('ERROR: 找不到 <g id="graph0">'); sys.exit(1)
svg = svg[:n] + insert + svg[n:]
open(OUT, 'w', encoding='utf-8').write(svg)
print('已生成:', OUT)
print('色带:', bands)
print('插入于 graph0 之前, 原 transform 保留')

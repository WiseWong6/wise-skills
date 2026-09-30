#!/usr/bin/env python3
"""Deterministic original-photo compositing; no generative model calls."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import os
import re
import shutil
import sys
import tempfile

try:
    import numpy as np
    from PIL import Image, ImageOps, ImageDraw
except ImportError as exc:
    raise SystemExit(f"缺少制作依赖：{exc.name}。请配置 Python 3、Pillow、NumPy；脚本不会自动安装。")

W, H, HALF, SS = 1800, 2400, 1200, 4
STYLES = {"puzzle": ("拼图版",390,390), "ticket": ("票根版",420,320)}

class PosterError(ValueError):
    pass

def require(condition, message):
    if not condition:
        raise PosterError(message)

def paper():
    rng = np.random.default_rng(20260925)
    coarse = Image.fromarray(rng.integers(90,166,(150,113),dtype=np.uint8)).resize((W,H),Image.Resampling.BICUBIC)
    fine = rng.normal(0,.63,(H,W)).astype(np.float32)
    tone = (np.asarray(coarse,dtype=np.float32)-128)*.027 + fine
    arr = np.clip(np.array([246,242,232],np.float32)+tone[:,:,None],0,255).astype(np.uint8)
    im = Image.fromarray(arr)
    # Extremely faint short fibers, no decorative marks or lighting gradients.
    layer = Image.new('RGBA',(W,H))
    d=ImageDraw.Draw(layer)
    for _ in range(17000):
        x,y=rng.integers(0,W),rng.integers(0,H)
        dx,dy=rng.integers(-3,4),rng.integers(-7,8)
        d.line((int(x),int(y),int(x+dx),int(y+dy)),fill=(163,147,118,int(rng.integers(3,10))),width=1)
    return np.asarray(Image.alpha_composite(im.convert('RGBA'),layer).convert('RGB')).copy()

def bezier(p0,p1,p2,p3,n=32):
    t=np.linspace(0,1,n)[:,None]
    return (1-t)**3*p0+3*(1-t)**2*t*p1+3*(1-t)*t*t*p2+t**3*p3

def edge(length, kind, exterior=False):
    if kind=='puzzle':
        if exterior: return np.array([[0.,0.],[length,0.]])
        # Shared master path: parameter is distance along edge, then outward depth.
        segs=[[(.34,0),(.41,0),(.445,.014),(.42,.055)],
              [(.42,.055),(.35,.14),(.405,.175),(.50,.175)],
              [(.50,.175),(.595,.175),(.65,.14),(.58,.055)],
              [(.58,.055),(.555,.014),(.59,0),(.66,0)]]
        return np.vstack(([[0,0]],*[bezier(*np.array(s)) for s in segs],[[1,0]]))*length
    # Rounded perforation cuts. Adjacent cells use the SAME edge in reverse.
    pitch=40.*min(1.,length/320); radius=pitch/4; pts=[[0.,0.]]
    centers=np.arange(pitch/2,length,pitch)
    for k,center in enumerate(centers):
        pts.append([center-radius,0.])
        sign=-1 if exterior else (1 if k%2==0 else -1)
        for angle in np.linspace(np.pi,0,25):
            pts.append([center+radius*np.cos(angle),sign*radius*np.sin(angle)])
    pts.append([float(length),0.])
    return np.array(pts)


def layout(count, kind):
    require(isinstance(count,int) and count>0, '至少需要一张照片')
    cols=math.ceil(math.sqrt(count)); rows=math.ceil(count/cols)
    cells=[]
    for r in range(rows):
        length=min(cols,count-len(cells)); start=(cols-length)//2
        cells.extend((r,c) for c in range(start,start+length))
    _,bw,bh=STYLES[kind]
    scale=min(1.,W*.7/(cols*bw),H*.6/(rows*bh))
    cw,ch=math.floor(bw*scale),math.floor(bh*scale)
    require(min(cw,ch)>=32, '照片数量过多，固定画幅内无法保留有效碎片边缘；请分批制作')
    return cells,cols,rows,cw,ch


def connected_cells(cells):
    pending=set(cells); stack=[pending.pop()]
    while stack:
        r,c=stack.pop()
        for other in [(r-1,c),(r+1,c),(r,c-1),(r,c+1)]:
            if other in pending:
                pending.remove(other); stack.append(other)
    return not pending


def masks(count,kind):
    cells,cols,rows,cw,ch=layout(count,kind)
    require(connected_cells(cells),'拼接单元不连通')
    occupied=set(cells); width,height=cols*cw,rows*ch
    # Signed 32-bit labels avoid a hidden 255-photo indexing limit.
    label=Image.new('I',(width*SS,height*SS),count)
    draw=ImageDraw.Draw(label); vertical={}; horizontal={}
    for r,c in cells:
        for key in [(r,c),(r,c+1)]:
            if key in vertical: continue
            rr,cc=key
            left=(rr,cc-1) in occupied; right=(rr,cc) in occupied
            e=edge(ch,kind,not(left and right))
            sign=1 if left else -1
            vertical[key]=np.column_stack((cc*cw+e[:,1]*sign,rr*ch+e[:,0]))
        for key in [(r,c),(r+1,c)]:
            if key in horizontal: continue
            rr,cc=key
            above=(rr-1,cc) in occupied; below=(rr,cc) in occupied
            e=edge(cw,kind,not(above and below))
            sign=1 if above else -1
            horizontal[key]=np.column_stack((cc*cw+e[:,0],rr*ch+e[:,1]*sign))
    for i,(r,c) in enumerate(cells):
        points=np.vstack((horizontal[r,c],vertical[r,c+1],horizontal[r+1,c][::-1],vertical[r,c][::-1]))
        draw.polygon([tuple(p*SS) for p in points],fill=i)
    hi=np.asarray(label)
    counts=np.stack([(hi==i).reshape(height,SS,width,SS).sum((1,3)) for i in range(count+1)]).astype(np.uint16)
    alpha=(counts*255//(SS*SS)).astype(np.uint8)
    residual=255-alpha.astype(np.int32).sum(axis=0)
    yy,xx=np.indices((height,width))
    alpha[counts.argmax(axis=0),yy,xx]+=residual.astype(np.uint8)
    require(np.all(alpha.astype(np.uint32).sum(axis=0)==255),'边界覆盖量不互补')
    require(all(np.any(a==255) for a in alpha[:-1]),'存在空碎片')
    # Every paper pixel must connect to outside; enclosed paper is a hole.
    exterior=np.pad((alpha[-1]>0).astype(np.uint8),1,constant_values=1)
    exterior_image=Image.fromarray(exterior).copy()
    ImageDraw.floodfill(exterior_image,(0,0),2,thresh=0)
    require(not np.any(np.asarray(exterior_image)==1),'拼接内部存在空洞或缝隙')
    return alpha,{'cells':cells,'cell_size':[cw,ch],'assembly_size':[width,height]}


def blend(fg,bg,alpha):
    a=alpha.astype(np.uint32)[:,:,None]
    return ((fg.astype(np.uint32)*a+bg.astype(np.uint32)*(255-a)+127)//255).astype(np.uint8)


def open_photo(path):
    with Image.open(path) as source:
        require(getattr(source,'n_frames',1)==1,'仅支持静态照片，不支持多帧图片')
        return ImageOps.exif_transpose(source).convert('RGB')


def numeric_sequence(value,length,field):
    require(isinstance(value,list) and len(value)==length,f'{field} 必须是 {length} 个数值')
    require(all(type(x) in (int,float) and math.isfinite(x) for x in value),f'{field} 含非法数值')
    return value


def validate_config(config):
    require(isinstance(config,dict),'配置必须为对象')
    photos=config.get('photos')
    require(isinstance(photos,list) and bool(photos),'photos 必须为非空照片数组')
    styles=config.get('styles',['puzzle','ticket'])
    require(isinstance(styles,list) and bool(styles),'styles 不能为空')
    require(all(isinstance(s,str) and s in STYLES for s in styles),'未知样式')
    require(len(styles)==len(set(styles)),'样式不能重复')
    normalized=[]
    for i,item in enumerate(photos):
        require(isinstance(item,dict),f'第 {i+1} 项照片配置不是对象')
        require(isinstance(item.get('path'),str),f'第 {i+1} 项缺少照片路径')
        path=Path(item['path'])
        require(path.is_absolute() and path.is_file(),f'照片不存在或不是绝对路径：{path}')
        box=numeric_sequence(item.get('crop_box'),4,'crop_box')
        center=numeric_sequence(item.get('fragment_center'),2,'fragment_center')
        require(all(0<=x<=1 for x in center),'碎片中心必须在 0～1 之间')
        with open_photo(path) as im:
            iw,ih=im.size
        x0,y0,x1,y1=box
        require(0<=x0<x1<=iw and 0<=y0<y1<=ih,f'裁切框越界：{path.name}')
        require(abs((x1-x0)/(y1-y0)-1.5)<1e-6,f'裁切框必须为 3:2：{path.name}')
        name=item.get('name',path.stem)
        require(isinstance(name,str) and bool(name.strip()),'照片名称必须为非空字符串')
        name=re.sub(r'[\x00-\x1f/\\:*?"<>|]','_',name).strip('. ')[:80] or '照片'
        normalized.append({'path':str(path),'name':name,'crop_box':box,'fragment_center':center,'original_size':[iw,ih],'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    for style in styles: layout(len(normalized),style)
    return normalized,styles


def prepare_photo(item):
    path=Path(item['path'])
    require(hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256'],'输入照片在制作期间发生变化')
    with open_photo(path) as image:
        return np.asarray(image.resize((W,HALF),Image.Resampling.LANCZOS,box=item['crop_box'])).copy()


def equal(actual,expected,message):
    require(np.array_equal(actual,expected),message)


def pixel_digest(pixels,mask):
    return hashlib.sha256(pixels.tobytes()+mask.tobytes()).hexdigest()


def render_style(photos,style,dest,bg):
    folder=dest/STYLES[style][0]; folder.mkdir()
    alpha,geometry=masks(len(photos),style)
    mw,mh=geometry['assembly_size']; ox,oy=(W-mw)//2,(H-mh)//2
    accumulator=bg[oy:oy+mh,ox:ox+mw].astype(np.uint32)*alpha[-1,:,:,None].astype(np.uint32)
    pieces=[]; records=[]; digits=max(2,len(str(len(photos)+1)))
    for i,item in enumerate(photos):
        photo=prepare_photo(item)
        ys,xs=np.where(alpha[i]>0)
        x0,x1=int(xs.min()),int(xs.max()+1); y0,y1=int(ys.min()),int(ys.max()+1)
        mask=alpha[i,y0:y1,x0:x1]; ph,pw=mask.shape
        wanted_x=round(item['fragment_center'][0]*W-pw/2)
        wanted_y=round(item['fragment_center'][1]*HALF-ph/2)
        sx=max(0,min(wanted_x,W-pw)); sy=max(0,min(wanted_y,HALF-ph))
        pixels=photo[sy:sy+ph,sx:sx+pw].copy()
        tx,ty=(W-pw)//2,(HALF-ph)//2
        top=blend(pixels,bg[ty:ty+ph,tx:tx+pw],mask)
        hole=blend(bg[HALF+sy:HALF+sy+ph,sx:sx+pw],pixels,mask)
        canvas=bg.copy(); canvas[HALF:]=photo
        canvas[ty:ty+ph,tx:tx+pw]=top
        canvas[HALF+sy:HALF+sy+ph,sx:sx+pw]=hole
        file=folder/f'{i+1:0{digits}d}_{item["name"]}.png'
        Image.fromarray(canvas).save(file,dpi=(300,300))
        with Image.open(file) as image: saved=np.asarray(image).copy()
        require(saved.shape==(H,W,3),'成品尺寸错误')
        equal(saved,canvas,'保存后的海报像素发生改变')
        # Check all pixels, including partial coverage, using explicit arithmetic.
        weight=mask.astype(np.float64)[:,:,None]/255
        expected_top=np.floor(pixels*weight+bg[ty:ty+ph,tx:tx+pw]*(1-weight)+.5).astype(np.uint8)
        expected_hole=np.floor(bg[HALF+sy:HALF+sy+ph,sx:sx+pw]*weight+pixels*(1-weight)+.5).astype(np.uint8)
        equal(saved[ty:ty+ph,tx:tx+pw],expected_top,'上方裁片或半透明边缘不一致')
        equal(saved[HALF+sy:HALF+sy+ph,sx:sx+pw],expected_hole,'原位缺口或半透明边缘不一致')
        photo[sy:sy+ph,sx:sx+pw]=expected_hole
        equal(saved[HALF:],photo,'下半区缺口以外的照片被改变')
        top_bg=bg[:HALF].copy(); top_bg[ty:ty+ph,tx:tx+pw]=expected_top
        equal(saved[:HALF],top_bg,'上半区纸面或位置错误')
        accumulator[y0:y1,x0:x1]+=pixels.astype(np.uint32)*mask[:,:,None].astype(np.uint32)
        pieces.append((pixels,mask,(x0,y0,x1,y1)))
        records.append({'file':file.name,'input':item,'source_box_in_lower_half':[sx,sy,sx+pw,sy+ph], 'top_box':[tx,ty,tx+pw,ty+ph],'hole_box':[sx,HALF+sy,sx+pw,HALF+sy+ph], 'edge_adjustment':[sx-wanted_x,sy-wanted_y],'assembly_box':[ox+x0,oy+y0,ox+x1,oy+y1],'fragment_and_mask_sha256':pixel_digest(pixels,mask),'checks':'PASS including partial-alpha edges'})
    result=bg.copy(); result[oy:oy+mh,ox:ox+mw]=((accumulator+127)//255).astype(np.uint8)
    final=folder/f'{len(photos)+1:0{digits}d}_完整拼接.png'
    Image.fromarray(result).save(final,dpi=(300,300))
    with Image.open(final) as image: actual=np.asarray(image).copy()
    equal(actual,result,'拼接图保存结果不一致')
    # Independent float compositor verifies shared-edge pixels as well as interiors.
    expected=bg[oy:oy+mh,ox:ox+mw].astype(np.float64)*(alpha[-1,:,:,None]/255.)
    for pixels,mask,(x0,y0,x1,y1) in pieces:
        expected[y0:y1,x0:x1]+=pixels*(mask[:,:,None]/255.)
        interior=mask==255
        equal(actual[oy+y0:oy+y1,ox+x0:ox+x1][interior],pixels[interior],'最终拼接改变了原裁片')
    equal(actual[oy:oy+mh,ox:ox+mw],np.floor(expected+.5).astype(np.uint8),'最终拼接的半透明接边有误')
    require(len(list(folder.glob('*.png')))==len(photos)+1,'输出图片数量错误')
    return {'style':style,**geometry,'geometry_checks':'PASS: complementary, connected, no enclosed holes','assembly_pixel_checks':'PASS including shared alpha edges','photos':records,'assembly_file':final.name}


def publish(stage,requested):
    # Reserve a NEW empty directory exclusively, then replace only our reservation.
    version=1
    while True:
        target=requested if version==1 else requested.with_name(f'{requested.name}-v{version}')
        try:
            target.mkdir()
            break
        except FileExistsError:
            version+=1
    try:
        os.replace(stage,target)
    except BaseException:
        target.rmdir()
        raise
    return target


def render(config,output):
    photos,styles=validate_config(config)
    requested=Path(output).expanduser().absolute()
    require(bool(requested.name) and requested.name not in ('.','..'),'输出目录无效')
    requested.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix=f'.{requested.name}-制作中-',dir=requested.parent))
    try:
        bg=paper()
        report={'status':'complete','canvas':[W,H],'split_y':HALF,'image_count':len(styles)*(len(photos)+1),'versions':[]}
        for style in styles:
            report['versions'].append(render_style(photos,style,stage,bg))
        for item in photos:
            require(hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()==item['sha256'],'输入照片发生改变，不发布本批次')
        (stage/'制作检查.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        target=publish(stage,requested)
        return {'status':'complete','output':str(target),'image_count':report['image_count']}
    finally:
        if stage.exists(): shutil.rmtree(stage)


def main():
    parser=argparse.ArgumentParser(description='记忆碎片摄影海报：原照片精确裁切')
    subs=parser.add_subparsers(dest='command',required=True)
    inspect=subs.add_parser('inspect'); inspect.add_argument('paths',nargs='+')
    make=subs.add_parser('render'); make.add_argument('--config',required=True); make.add_argument('--output',required=True)
    args=parser.parse_args()
    try:
        if args.command=='inspect':
            result=[]
            for path in args.paths:
                with open_photo(path) as im:
                    result.append({'path':str(Path(path).absolute()),'oriented_size':list(im.size)})
        else:
            config=json.loads(Path(args.config).read_text(encoding='utf-8'))
            result=render(config,args.output)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (PosterError,OSError,ValueError) as exc:
        print(json.dumps({'status':'failed','error':str(exc)},ensure_ascii=False),file=sys.stderr)
        return 1
    return 0


if __name__=='__main__':
    sys.exit(main())

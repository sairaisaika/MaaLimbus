"""Generate a public-text-only preview of feature-local wiki diagrams."""
import argparse
import html
import json
import re
from pathlib import Path
from make_wiki_mermaid_check import mermaid_blocks, MERMAID_URL

ROOT=Path(__file__).resolve().parents[1]


def render(wiki, language='zh_cn'):
    blocks=[b for b in mermaid_blocks(wiki) if b['page'].startswith(language+'/')]
    chapters={}
    entries=[]
    for index,block in enumerate(blocks):
        path=wiki/block['page'];lines=path.read_text(encoding='utf-8').splitlines()
        heading=next((line.lstrip('# ').strip() for line in reversed(lines[:block['start']-1])
                      if re.match(r'^#{1,3} ',line)),path.stem)
        chapter=lines[0].lstrip('# ');chapters.setdefault(chapter,[]).append(index)
        entries.append(dict(block,heading=heading,chapter=chapter))
    zh=language=='zh_cn'
    title='MaaLimbus：总览与功能分图' if zh else 'MaaLimbus: overview and feature diagrams'
    intro=('总览用于导航；分图解释每段功能的交互、守卫和失败恢复。图可展开查看，完整说明和未验收边界在对应 wiki 小节。'
           '神经影子推理不等于生产输入，菜单导航不等于刷本完成，语法通过不等于通关。'
           if zh else 'Overview diagrams navigate; local views explain feature interactions, guards and recovery. '
           'Expand a diagram; full prose and unverified boundaries remain in its wiki section. '
           'Shadow inference is not production control, navigation is not farming, and syntax is not a clear.')
    out=['<!doctype html><html lang="'+('zh-CN' if zh else 'en')+'"><meta charset="utf-8">',
         '<title>'+title+'</title><style>body{font:16px system-ui;background:#f6f8fb;color:#172d42;margin:0 auto;padding:28px;max-width:1250px}h1{font-size:27px}p{line-height:1.6}nav{display:flex;flex-wrap:wrap;gap:12px;padding:18px 0}a{color:#075ba4}details{margin:16px 0;padding:18px;border:1px solid #cbd6e1;border-radius:10px;background:#fff}summary{cursor:pointer;font-weight:600;line-height:1.5}.diagram{overflow:auto;padding:16px 0}.diagram svg{max-width:none!important;min-width:850px;height:auto}.diagram.fit svg{width:100%!important;max-width:100%!important;min-width:0}.source{font:13px monospace;color:#4c6173}.hint{font-size:13px;color:#4c6173}button{border:1px solid #bbc9d6;border-radius:6px;padding:8px;background:#f3f7fb;cursor:pointer}.error{color:#ab2020}h2{margin-top:38px}</style>',
         '<h1>'+title+'</h1><p>'+intro+'</p><p id="status">'+('图索引已生成。展开时渲染。' if zh else 'Diagram index ready. Expand to render.')+'</p><nav>']
    for i,chapter in enumerate(chapters):out.append(f'<a href="#chapter-{i}">{html.escape(chapter)}</a>')
    out.append('</nav>')
    for i,(chapter,indices) in enumerate(chapters.items()):
        out.append(f'<h2 id="chapter-{i}">{html.escape(chapter)}</h2>')
        for index in indices:
            entry=entries[index]
            out.append(f'<details data-index="{index}" id="diagram-{index}"><summary>{html.escape(entry["heading"])} · {html.escape(entry["type"])}</summary>')
            out.append('<p class="source">'+html.escape('docs/wiki/'+entry['page']+':'+str(entry['start']))+'</p>')
            out.append('<p class="hint">'+('窄窗口可左右滚动；切换缩放查看整体。' if zh else 'Scroll horizontally in narrow windows; toggle fit to see the whole view.')+'</p>')
            out.append('<button class="fit-toggle">'+('切换整体 / 可读大小' if zh else 'Toggle fit / readable size')+'</button><div class="diagram"></div></details>')
    payload=json.dumps(entries,ensure_ascii=False).replace('<',r'\u003c')
    out.append('<script type="module">import mermaid from '+json.dumps(MERMAID_URL)+';')
    out.append('mermaid.initialize({startOnLoad:false,securityLevel:"strict"});const blocks='+payload+';')
    out.append('''let rendered=0;document.querySelectorAll('details').forEach(section=>{
      section.querySelector('.fit-toggle').addEventListener('click',()=>section.querySelector('.diagram').classList.toggle('fit'));
      section.addEventListener('toggle',async()=>{if(!section.open || section.dataset.rendered)return;
        section.dataset.rendered='pending';const i=Number(section.dataset.index);const target=section.querySelector('.diagram');
        try{const result=await mermaid.render('view-'+i,blocks[i].code);target.innerHTML=result.svg;
          const svg=target.querySelector('svg');svg.style.width=Math.max(850,svg.viewBox.baseVal.width)+'px';
          section.dataset.rendered='true';rendered++;document.querySelector('#status').textContent=rendered+' / '+blocks.length+' diagrams rendered';
        }catch(e){section.dataset.rendered='failed';target.classList.add('error');target.textContent=String(e);}
      });
    });</script></html>''')
    return ''.join(out)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=ROOT/'build/wiki-views/engineering.html')
    parser.add_argument('--language',choices=('zh_cn','en_us'),default='zh_cn')
    args=parser.parse_args();args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(render(ROOT/'docs/wiki',args.language),encoding='utf-8')
    print('wrote',args.out)


if __name__=='__main__':main()

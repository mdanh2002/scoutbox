import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from django.utils import timezone
from django.core.files.base import ContentFile
from portal.models import PerformanceRun, UsageMetric, SearchSource
from .ai import generate_with
from .search import search_source, UA
from .freshness import analyze_url_age


def _ollama_direct(base_url, model, prompt, timeout=120):
    start=time.time()
    r=requests.post(base_url.rstrip('/')+'/api/generate',json={'model':model,'prompt':prompt,'stream':False},timeout=timeout)
    r.raise_for_status(); data=r.json()
    return data.get('response',''), int((time.time()-start)*1000), int(data.get('prompt_eval_count') or 0), int(data.get('eval_count') or 0)


def run_lab(kind, provider='', model='', device='', input_text='', input_url='', upload=None, temp_ollama_url=''):
    run=PerformanceRun.objects.create(kind=kind,provider=provider,model=model,device=device,input_text=input_text[:20000],input_url=input_url)
    started=time.time()
    try:
        if kind=='search':
            source=SearchSource.objects.get(name=provider)
            results,err=search_source(source,input_text or 'embedded reverse engineering remote',limit=10,usage_category='lab')
            if err: raise RuntimeError(err)
            run.output_text=json.dumps(results,indent=2)[:30000]
        elif kind=='scrape':
            r=requests.get(input_url,headers={'User-Agent':UA},timeout=20); r.raise_for_status()
            run.bytes_downloaded=len(r.content); UsageMetric.objects.create(category='lab',provider='direct',stage='scrape',requests=1,pages=1,latency_ms=int((time.time()-started)*1000),bytes_downloaded=run.bytes_downloaded,metadata={'url':input_url}); soup=BeautifulSoup(r.content,'html.parser')
            for x in soup(['script','style','noscript']): x.extract()
            run.output_text=' '.join(soup.stripped_strings)[:30000]
        elif kind=='age_check':
            if not input_url: raise RuntimeError('Enter a job / opportunity URL for age analysis.')
            data=analyze_url_age(input_url)
            lines=[
                f"Verdict: {data['label']}",
                f"Estimated age: {data['age_days']} day(s)" if data['age_days'] is not None else 'Estimated age: unknown',
                f"Estimated date: {data['estimated_date'] or 'unknown'}",
                f"Confidence: {data['confidence']}%",
                f"Reasoning: {data['reasoning']}",
                data.get('fetch_note',''),
                '', 'Evidence:'
            ]
            for sig in data.get('signals',[]):
                lines.append(f"- {sig['label']}: {sig['date']} · confidence {sig['confidence']}%" + (f" · {sig['note']}" if sig.get('note') else ''))
            run.output_text='\n'.join(x for x in lines if x is not None)[:30000]
            run.metadata=data
        elif kind=='docx_to_pdf':
            if not upload or not upload.name.lower().endswith('.docx'): raise RuntimeError('Upload a DOCX for the conversion benchmark.')
            with tempfile.TemporaryDirectory() as td:
                src=Path(td)/Path(upload.name).name; src.write_bytes(upload.read())
                lo=shutil.which('libreoffice') or shutil.which('soffice')
                if not lo: raise RuntimeError('LibreOffice is not installed in this runtime')
                p=subprocess.run([lo,'--headless','--convert-to','pdf','--outdir',td,str(src)],capture_output=True,text=True,timeout=90)
                pdf=src.with_suffix('.pdf')
                if p.returncode or not pdf.exists(): raise RuntimeError((p.stderr or p.stdout)[-1000:])
                run.bytes_downloaded=pdf.stat().st_size
                run.output_file.save(pdf.name,ContentFile(pdf.read_bytes()),save=False)
                run.output_text=f'Converted {src.name} -> {pdf.name}; output {pdf.stat().st_size} bytes.'
                run.metadata={'source_name':src.name,'output_name':pdf.name,'output_bytes':pdf.stat().st_size}
        else:
            prompts={
                'chat': input_text or 'Say hello and identify yourself briefly.',
                'summarize': 'Summarize the following content concisely and preserve technical details:\n\n'+input_text,
                'extract': 'Extract company, role, location, remote eligibility, engagement type, compensation, technologies, contact email, and hiring-process clues. Do not invent missing values.\n\n'+input_text,
                'rank': 'Score this opportunity 0-100 for a niche embedded/reverse-engineering/retro-computing candidate in Singapore and explain the score concisely.\n\n'+input_text,
            }
            prompt=prompts.get(kind,input_text)
            if provider=='ollama' and temp_ollama_url:
                out,lat,tin,tout=_ollama_direct(temp_ollama_url,model,prompt)
                run.output_text=out; run.latency_ms=lat; run.tokens_in=tin; run.tokens_out=tout
                UsageMetric.objects.create(category='lab',provider='ollama',model=model,stage='lab_direct',requests=1,tokens_in=tin,tokens_out=tout,latency_ms=lat,metadata={'temporary_url':temp_ollama_url})
            else:
                before=timezone.now(); out=generate_with(provider,model,prompt,stage='lab')
                run.output_text=out; run.latency_ms=int((timezone.now()-before).total_seconds()*1000)
        if not run.latency_ms: run.latency_ms=int((time.time()-started)*1000)
        run.ok=True
    except Exception as e:
        run.ok=False; run.error=str(e); run.output_text=''
        run.latency_ms=int((time.time()-started)*1000)
    run.save()
    return run

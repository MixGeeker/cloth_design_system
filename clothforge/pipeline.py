"""One input revision drives geometry, BOM, instructions, and traceable manifests."""
import argparse,csv,hashlib,json,shutil,tempfile
from pathlib import Path
from .contracts import validate_analysis,validate_profile,canonical_hash,analyze_images
from .patterns import generate_patterns,seam_graph,construction_openings
from .rigid import generate_rigid
from .export import svg_pattern,pattern_pdf,instructions_pdf

def write_json(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def _build_into(spec,profile,outdir):
 validate_analysis(spec);validate_profile(profile)
 if spec.get('user_overrides') or any('closure' in c for c in spec['components']):
  raise ValueError('Engineering review required: automatic closure/material override recompilation is not implemented')
 outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
 revision=canonical_hash({'spec':spec,'profile':profile,'engine':'0.1.0'})
 components={c['id']:c for c in spec['components']}
 allowed={c['id'] for c in spec['components'] if c['status']=='generate'}
 all_patterns=generate_patterns(profile)
 patterns=[p for p in all_patterns if p['component_id'] in allowed]
 all_rigid=generate_rigid(profile,outdir)
 rigid=[r for r in all_rigid if r['component_id'] in allowed]
 for r in all_rigid:
  if r['component_id'] not in allowed:(outdir/r['file']).unlink()
 write_json(outdir/'rigid_manifest.json',{'units':'mm','parts':rigid})
 write_json(outdir/'analysis.json',spec);write_json(outdir/'profile.json',profile);write_json(outdir/'patterns.json',patterns)
 for p in patterns:svg_pattern(p,outdir/(p['id']+'.svg'))
 pattern_pdf(patterns,outdir/'patterns_1to1.pdf',profile['id'])
 # Assembly order is independent from the seam graph; all references resolve.
 stages=[('cut',[],'先用坯布制作；纸样实际尺寸打印，检查20mm标尺'),
 ('torso',['cut'],'按主体片标记缝合，暂留闭合口；先试穿再锁定装饰带位置'),
 ('flounce',['torso'],'连接下摆各片，接到主体下缘；检查腰臀活动余量'),
 ('sleeves',['cut'],'分离上臂袖、前臂袖和袖口各自试穿；弹性固定不得勒紧'),
 ('trim',['torso','flounce'],'缝制领带、颈带、髋侧饰片与饰带，手缝定位'),
 ('print',[],'打印几何饰件原型，检查边缘并打磨；不直接用于承重'),
 ('mount',['print','sleeves','trim'],'通过孔/槽可拆卸缝固饰件；颈部接口应能快速脱开'),
 ('review',['mount'],'复核抬臂、坐下、深呼吸、穿脱及视线；未通过不得定版')]
 stage_components={'cut':bool(patterns),'torso':'torso' in allowed,'flounce':'hip_flounce' in allowed,'sleeves':bool(allowed & {'upper_sleeve','forearm_sleeve','cuff'}),'trim':bool(allowed & {'upper_band','tie','neckband','hip_insert'}),'print':bool(rigid),'mount':bool(rigid),'review':True}
 active={i for i,_,_ in stages if stage_components[i]}
 assembly=[{'id':i,'depends_on':[d for d in deps if d in active],'instruction':s} for i,deps,s in stages if i in active]
 seams=[]
 for p in patterns:
  for name,points in p.get('seams',{}).items():seams.append({'piece':p['id'],'edge':name,'points_mm':points})
 piece_ids={p['id'] for p in patterns}
 joins=[j for j in seam_graph(all_patterns) if j['a']['piece_id'] in piece_ids and j['b']['piece_id'] in piece_ids]
 openings=[o for o in construction_openings(all_patterns) if o.get('piece_id') in piece_ids]
 graph={'revision':revision,'edges':seams,'joins':joins,'openings':openings,'assembly':assembly,'note':'参数化接缝配对；不是布料仿真；修改组件范围后需复核与既有服装的接口'}
 write_json(outdir/'assembly_graph.json',graph)
 rows=[]
 for c in spec['components']:
  pieces=[p for p in patterns if p['component_id']==c['id']]
  meshes=[r for r in rigid if r['component_id']==c['id']]
  rows.append({'component_id':c['id'],'label':c['label'],'status':c['status'],'material':c['material'],
   'cut_quantity':sum(p['quantity'] for p in pieces),'printed_quantity':len(meshes),'files':';'.join([p['id']+'.svg' for p in pieces]+[r['file'] for r in meshes]),
   'note':'未核算排料耗损；须试样确认' if pieces else ('装饰打印原型；须另核缝固织带' if meshes else '见人工/采购范围')})
 with (outdir/'bom.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 lines=[f'服装工程原型 制作说明 {profile["id"]}',f'数据来源模式 {spec["mode"]}',f'版本 {revision[:16]}','仅限样衣和打印原型审查，未经实物试穿或工厂验证。','身体数据均为虚构成人测试值，单位mm。','本版从已人工审阅的结构规格生成；不等于任意新图片识别。','']
 lines+=['测量 '+k+' = '+str(profile[k]) for k in ('height','bust','waist','hip','shoulder','back_waist_length','front_waist_length','arm_length')]
 lines+=['','组件登记表尚非完整采购BOM；缝线、闭合件、弹性带、衬料和织带待试样核量。','制造/采购范围']+[c['label']+'：'+c['status']+'；'+c['material'] for c in spec['components']]
 lines+=['','纸样注意事项','黑色实线为裁剪线，蓝色虚线为缝合线。已包含所标缝份，不重复添加。','PDF每页为实际纸样大小；大幅打印或用阅读器海报分割，禁止适合页面。','SVG width/height为毫米；导入其他软件后再次核查20mm标尺。']
 for p in patterns:lines += [p['id']+' 裁剪 '+str(p['quantity'])+'片']+p.get('notes',[])
 lines+=['','组装顺序']+[str(i+1)+' '+s['instruction'] for i,s in enumerate(assembly)]
 lines+=['','未确定事项']+[u['question']+' '+u['hypothesis'] for u in spec['unknowns']]
 lines+=['','限制']+spec['limitations']
 instructions_pdf(lines,outdir/'instructions_zh.pdf')
 (outdir/'instructions_zh.txt').write_text('\n'.join(lines)+'\n')
 generated={p['component_id'] for p in patterns}|{r['component_id'] for r in rigid}
 missing=[c['id'] for c in spec['components'] if c['status']=='generate' and c['id'] not in generated]
 if missing:raise ValueError('Missing generated components '+str(missing))
 files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in outdir.iterdir() if p.is_file() and p.name!='manifest.json'}
 manifest={'schema_version':'1.0','revision':revision,'profile_id':profile['id'],'engine_version':'0.1.0','references':spec['references'],'analysis_mode':spec['mode'],'reference_status':spec['reference_status'],'files_sha256':files,'pattern_count':len(patterns),'rigid_count':len(rigid),'validation':'digital prototype checks only; no physical fitting','unresolved':spec['unknowns']}
 write_json(outdir/'manifest.json',manifest)
 return manifest

def build(spec,profile,outdir):
 outdir=Path(outdir)
 if outdir.exists() and any(outdir.iterdir()):
  raise FileExistsError('Output directory must be empty; choose a new revision directory')
 outdir.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='.cloth-build-',dir=outdir.parent) as tmp:
  manifest=_build_into(spec,profile,Path(tmp))
  shutil.copytree(tmp,outdir,dirs_exist_ok=True)
 return manifest

def main():
 p=argparse.ArgumentParser(description='No runtime vision model: generates from explicitly authored specs')
 p.add_argument('--analysis',default='examples/neutral.analysis.json');p.add_argument('--profiles',default='examples/profiles.json');p.add_argument('--out',default='build');p.add_argument('--images',nargs='+');p.add_argument('--backend',default='live',choices=['live','replay'])
 args=p.parse_args()
 spec=analyze_images(args.images,args.backend,args.analysis) if args.images else validate_analysis(json.loads(Path(args.analysis).read_text()))
 for profile in json.loads(Path(args.profiles).read_text()):
  m=build(spec,profile,Path(args.out)/profile['id']);print(profile['id'],m['revision'],m['pattern_count'],m['rigid_count'])
if __name__=='__main__':main()

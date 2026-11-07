import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from champollion.format import parse_work
from champollion.profile import load_profile
from champollion.summary import _section, basis_hash, section_units, summary_prompt_spec, validate

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / 'tests/fixtures/summary'

class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.work = parse_work(FIX / 'work.md')
        self.profile = load_profile(ROOT / 'profiles/mouseia.json')
        self.obj = {
            'schema':'champollion-summary/1','work':'example','title':'Example','author':'An author',
            'basis':{'register':'plain','sha256':basis_hash(_section(self.work,'plain',self.profile)),'units':3},
            'aid':'Machine assisted','generated':'2026-01-01','review':{'status':'reviewed','by':'Reviewer','date':'2026-01-01','notes':'Checked'},
            'summary':{'gist':'A gist.','overview':'An overview.','context':'A context.','key_facts':{},
                       'key_ideas':[{'id':i,'title':'Idea','explanation':'Explanation','units':[1]} for i in ('one','two','three')],
                       'units':[{'n':n,'label':label,'summary':'A summary','ideas':['one','two','three'] if n == 1 else []} for n,label,_ in section_units(self.work,'plain',self.profile)],
                       'figures':[],'terms':[],'passages':[{'unit':2,'text':'A "quoted" passage - here.','why':'Important.'}]},
            'index':{'genres':['story'],'forms':['prose'],'themes':['one','two','three'],'concepts':[], 'people':[], 'places':[], 'period':'Unknown','keywords':[],'related':[]}}
    def codes(self): return {f.code for f in validate(self.obj,self.work,self.profile,{'example','other'})}
    def test_valid_and_units(self):
        self.assertEqual(self.obj, json.loads((FIX / "passing.json").read_text()))
        self.assertEqual(self.codes(),set())
        self.assertEqual([(n,l) for n,l,_ in section_units(self.work,'plain',self.profile)],[(1,''),(2,'First'),(3,'Second')])
        self.assertEqual(summary_prompt_spec(),json.loads((ROOT/'src/champollion/schemas/summary-1.json').read_text()))
    def test_codes(self):
        changes = {
            'SUM-SCHEMA': lambda o: o.pop('aid'),
            'SUM-WORK': lambda o: o.update(title='Wrong'),
            'SUM-STALE': lambda o: o['basis'].update(sha256='bad'),
            'SUM-UNITS': lambda o: o['summary']['units'][1].update(label='Wrong'),
            'SUM-LENGTH': lambda o: o['summary'].update(gist='word '*46),
            'SUM-XREF': lambda o: o['summary']['units'][0].update(ideas=['unknown']),
            'SUM-PASSAGE': lambda o: o['summary']['passages'][0].update(text='invented'),
            'SUM-RELATED': lambda o: o['index']['related'].append({'work':'missing','relation':'shares-theme','note':'Note'}),
            'SUM-SLUG': lambda o: o['index'].update(themes=['Not kebab','two','three']),
            'SUM-REVIEW': lambda o: o['review'].update(status='unreviewed'),
        }
        for code in changes:
            with self.subTest(code=code):
                self.obj = json.loads((FIX / (code + ".json")).read_text())
                self.assertIn(code,self.codes())
    def test_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root/'works').mkdir(); (root/'summaries').mkdir()
            (root/'works/example.md').write_text((FIX/'work.md').read_text())
            profile = str(ROOT/'profiles/mouseia.json')
            def run(*args):
                return subprocess.run([sys.executable,'-m','champollion','summary',*args],capture_output=True,text=True)
            args = ('check','--root',str(root),'--profile',profile,'--require','--json')
            result = run(*args); self.assertEqual(result.returncode,1,result.stderr)
            self.assertEqual(json.loads(result.stdout)['findings'][0]['code'],'SUM-MISSING')
            (root/'summaries/example.json').write_text(json.dumps(self.obj))
            result = run(*args); self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['counts']['errors'],0)
            result = run('units',str(root/'works/example.md'),'--json'); self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(len(json.loads(result.stdout)['units']),3)

class SummaryCorpusTests(unittest.TestCase):
    """Regressions found against a real legacy corpus."""
    def setUp(self):
        self.base = SummaryTests('test_cli'); self.base.setUp()
    def _root(self, temp):
        root = Path(temp); (root/'corpus/summaries').mkdir(parents=True)
        (root/'corpus/example.md').write_text((FIX/'work.md').read_text())
        other = (FIX/'work.md').read_text().replace('slug: example', 'slug: other', 1)
        (root/'corpus/other.md').write_text(other)
        (root/'corpus/SOURCES.md').write_text('# Sources\n\nA register of providers, not a work.\n')
        # A legacy work whose Original has a preamble the strict parser refuses.
        legacy = (FIX/'work.md').read_text().replace('slug: example', 'slug: legacy', 1).replace('## Original\n', '## Original\n\nA preamble line.\n', 1)
        (root/'corpus/legacy.md').write_text(legacy)
        obj = copy.deepcopy(self.base.obj)
        obj['index']['related'] = [{'work': 'other', 'relation': 'shares-theme', 'note': 'Note'}]
        (root/'corpus/summaries/example.json').write_text(json.dumps(obj))
        return root
    def run_cli(self, *args):
        return subprocess.run([sys.executable,'-m','champollion','summary',*args],capture_output=True,text=True)
    def test_selected_work_may_link_to_unselected_work(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self._root(temp)
            r = self.run_cli('check','--root',str(root),'--profile',str(ROOT/'profiles/mouseia.json'),'--dir','corpus/summaries','--json','corpus/example.md')
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
    def test_glob_skips_non_work_files_and_tolerates_legacy_original(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self._root(temp)
            r = self.run_cli('check','--root',str(root),'--profile',str(ROOT/'profiles/mouseia.json'),'--dir','corpus/summaries','--works-glob','corpus/*.md','--require','--json')
            self.assertEqual(r.returncode,1,r.stderr)
            missing = sorted(f['work'] for f in json.loads(r.stdout)['findings'] if f['code']=='SUM-MISSING')
            self.assertEqual(missing,['legacy','other'])

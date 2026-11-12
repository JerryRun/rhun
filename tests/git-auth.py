#!/usr/bin/env python3
import os, pathlib, subprocess, tempfile, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
NL = chr(10)
class Auth(unittest.TestCase):
 def test_prompts(self):
  for cancel in (False, True):
   with self.subTest(cancel=cancel), tempfile.TemporaryDirectory(prefix='rhun-auth-') as t:
    p=pathlib.Path(t);repo=p/'repo 中文';repo.mkdir();b=p/'bin';b.mkdir()
    real=subprocess.check_output(['which','git'],text=True).strip()
    env=dict(os.environ,HOME=t,XDG_CONFIG_HOME=str(p/'config'),XDG_STATE_HOME=str(p/'state'),PATH=str(b)+':'+os.environ['PATH'],GIT_CONFIG_NOSYSTEM='1')
    def git(*args):subprocess.run([real,'-C',str(repo),*args],env=env,check=True,capture_output=True)
    git('init','-q','-b','main');git('config','user.name','Test');git('config','user.email','t@t');(repo/'a').write_text('a');git('add','.');git('commit','-qm','init');git('remote','add','origin','https://example.invalid/a.git');git('config','branch.main.remote','origin');git('config','branch.main.merge','refs/heads/main')
    c=p/'config/rhun/config';c.parent.mkdir(parents=True);c.write_text(NL.join(['[updates]','check=false','[ui]','agents_panel=false','']))
    shim=['#!/usr/bin/env python3','import os,sys,subprocess','if "push" in sys.argv[1:]:',' u=subprocess.run([os.environ["GIT_ASKPASS"],"Username for https://example.invalid:"],capture_output=True,text=True)',' if u.returncode: sys.exit(1)',' v=subprocess.run([os.environ["GIT_ASKPASS"],"Password for https://example.invalid:"],capture_output=True,text=True)',' if v.returncode: sys.exit(1)',' open(os.path.join(os.environ["HOME"],"answer"),"w").write(u.stdout+v.stdout)',' sys.exit(0)','os.execv('+repr(real)+',['+repr(real)+']+sys.argv[1:])']
    (b/'git').write_text(NL.join(shim)+NL);(b/'git').chmod(0o755)
    cmds=['wait-git','cmd git_push','wait 800','print-palette']
    if cancel:
     cmds+=['key Escape']
    else:
     cmds+=['type test-user','wait 100']
     if env.get('RHUN_FCITX_ROOT'):
      # Enter the password prompt with Chinese mode active: secrets must bypass IME.
      cmds+=['key ctrl+alt+space','wait 150']
     cmds+=['key Return','wait 800','print-palette','type test-token','key Return']
    s=p/'script';s.write_text(NL.join(cmds+['wait 500','print-scm','quit','']))
    r=subprocess.run([str(ROOT/'build/rhun'),str(repo),'--headless','1100x800','--script',str(s)],env=env,capture_output=True,text=True,timeout=20)
    self.assertEqual(r.returncode,0,r.stderr);self.assertIn('Username for https://example.invalid:',r.stdout);self.assertNotIn('test-token',r.stdout+r.stderr)
    if cancel:self.assertFalse((p/'answer').exists())
    else:self.assertIn('Password for https://example.invalid:',r.stdout);self.assertEqual((p/'answer').read_text(),NL.join(['test-user','test-token','']))
if __name__=='__main__':unittest.main()

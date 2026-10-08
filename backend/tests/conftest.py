import os,tempfile
os.environ['LANCE_ROOT']=tempfile.mkdtemp(prefix='lance-tests-')

os.environ['LANCE_AUTH_ENABLED']='true'

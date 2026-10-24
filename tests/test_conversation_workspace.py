from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess
import unittest

from jinja2 import Environment, FileSystemLoader

ROOT=Path(__file__).resolve().parents[1]


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.identifiers=[]

    def handle_starttag(self,tag,attributes):
        value=dict(attributes).get('id')
        if value:self.identifiers.append(value)


class ConversationWorkspaceTests(unittest.TestCase):
    def test_template_keeps_one_instance_of_each_existing_control(self):
        html=Environment(loader=FileSystemLoader(ROOT/'templates')).get_template('index.html').render()
        parser=Elements();parser.feed(html)
        counts=Counter(parser.identifiers)
        self.assertFalse([name for name,count in counts.items() if count!=1])
        for name in ('listen','pauseMicrophone','cancelMicrophone','heardText','sendTranscript','askAfterListen',
                     'mode','conversationForm','conversationSend','actualVoiceName','actualVoiceCard',
                     'recordSeconds','say','chat','liveEnabled','controlKey','mediaShowVersions',
                     'mediaSources','mediaVersionsPanel','versionAudio','versionList'):
            self.assertEqual(counts[name],1,name)
        self.assertIn('data-view="conversation"',html)
        sidebar=html.split('<aside class="workspace-sidebar"',1)[1].split('</aside>',1)[0]
        for name in ('eyes','mouth','showConversation','tab-yeux','tab-bouche','controlKey','deploymentVersion'):
            self.assertIn('id="'+name+'"',sidebar,name)
        self.assertLess(sidebar.index('id="mouth"'),sidebar.index('class="workshop-tabs"'))
        self.assertNotIn('id="conversationForm"',sidebar)

    @unittest.skipUnless(shutil.which('node'),'Node requis pour tester le contrôleur web')
    def test_real_audio_source_is_independent_of_the_configured_engine(self):
        result=subprocess.run([shutil.which('node'),str(ROOT/'tests'/'voice-status-ui.cjs')],
                              capture_output=True,text=True,encoding='utf-8',timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

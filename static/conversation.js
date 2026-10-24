'use strict';
(() => {
 const list=document.getElementById('conversationLog'), status=document.getElementById('conversationStatus');
 window.BenderConversation={
  begin(text,source='Texte') {
   document.getElementById('conversationEmpty').hidden=true;
   const card=document.createElement('article');card.className='conversation-turn';
   const title=document.createElement('h3');title.textContent=`Vous · ${source} · ${new Date().toLocaleTimeString('fr-FR',{hour:'2-digit',minute:'2-digit'})}`;
   const question=document.createElement('p');question.className='conversation-question';question.textContent=text;
   const label=document.createElement('h3');label.textContent='Bender';
   const answer=document.createElement('p');answer.className='conversation-answer';answer.textContent='Transcription prête.';
   const note=document.createElement('p');note.className='conversation-note';
   const audioSource=document.createElement('p');audioSource.className='conversation-source';audioSource.hidden=true;
   card.append(title,question,label,answer,audioSource,note);list.append(card);
   while(list.children.length>20)list.firstElementChild.remove();
   list.scrollTop=list.scrollHeight;
   return {card,question,answer,source:audioSource,note,answered:false};
  },
  pending(turn,text) {turn.question.textContent=text;turn.answer.textContent='Réflexion en cours…';turn.note.textContent='';status.textContent='Bender prépare sa réponse.';document.getElementById('microphoneAnswer').textContent='Réflexion en cours…';},
  reply(turn,text) {turn.answer.textContent=text;turn.answered=true;status.textContent='Réponse reçue.';list.scrollTop=list.scrollHeight;document.getElementById('microphoneAnswer').textContent=text;},
  audio(turn,bundle,timings={}) {
   const result=window.BenderVoiceStatus.summarize(bundle),time=window.BenderVoiceStatus.timing(timings);
   turn.source.hidden=false;turn.source.textContent=`Audio : ${result.parts.map(p=>p.label).join(' → ')}${time?' · '+time:''}`;
   turn.source.dataset.source=result.primary.source;turn.source.title=result.primary.note;
  },
  error(turn,message) {if(!turn.answered){turn.answer.textContent='Aucune réponse reçue.';document.getElementById('microphoneAnswer').textContent=message;}turn.note.textContent=message;status.textContent=message;},
  status(message) {status.textContent=message;}
 };
})();

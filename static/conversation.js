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
   card.append(title,question,label,answer,note);list.append(card);
   while(list.children.length>20)list.firstElementChild.remove();
   list.scrollTop=list.scrollHeight;
   return {card,question,answer,note,answered:false};
  },
  pending(turn,text) {turn.question.textContent=text;turn.answer.textContent='Réflexion en cours…';turn.note.textContent='';status.textContent='Bender prépare sa réponse.';document.getElementById('microphoneAnswer').textContent='Réflexion en cours…';},
  reply(turn,text) {turn.answer.textContent=text;turn.answered=true;status.textContent='Réponse reçue.';list.scrollTop=list.scrollHeight;document.getElementById('microphoneAnswer').textContent=text;},
  error(turn,message) {if(!turn.answered){turn.answer.textContent='Aucune réponse reçue.';document.getElementById('microphoneAnswer').textContent=message;}turn.note.textContent=message;status.textContent=message;},
  status(message) {status.textContent=message;}
 };
})();

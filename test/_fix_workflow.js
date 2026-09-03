const fs = require('fs');
const p = 'd:/Документы/Manual/Нитология/test/n8n-workflow-message-classification.json';
const j = JSON.parse(fs.readFileSync(p, 'utf8'));

// Update Save to File node — dynamic filename per category: price.txt, consultation.txt, other.txt
const sf = j.nodes.find(n => n.name === 'Save to File');
sf.parameters.command = '={{ `echo "[${$json.date}] message=${$json.message_text} | summary=${$json.summary} | reply_draft=${$json.reply_draft} | status=${$json.status}" >> /home/vagrant/${$json.category}.txt` }}';

fs.writeFileSync(p, JSON.stringify(j, null, 2), 'utf8');
console.log('=== Command updated ===');
console.log(sf.parameters.command);
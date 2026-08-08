# Yapay Zeka ve Makine Ogrenimi

Yapay zeka (YZ), makinelerin insan benzeri zeki davranislar sergilemesini saglayan bilgisayar bilimi dalıdır. Makine ogrenimi ise yapay zekanin bir alt dalı olup, bilgisayarlarin acikca programlanmadan verilerden ogrenme yetenegini icerir.

## Makine Ogrenimi Turleri

### Gozetimli Ogrenme (Supervised Learning)
Gozetimli ogrenmede, modele etiketli veri seti verilir. Model, girdi ve cikti arasindaki iliskiyi ogrenmeye calisir. Siniflandirma (classification) ve regresyon (regression) gozetimli ogrenmenin iki temel turudur.

Ornekler: E-posta spam filtresi, ev fiyat tahmini, hastalık teshisi.

### Gozletimsiz Ogrenme (Unsupervised Learning)
Gozletimsiz ogrenmede, veriler etiketlenmemistir. Model, verideki gizli oruntuleri ve yapilari kesfetmeye calisir. Kumeleme (clustering) ve boyut indirgeme (dimensionality reduction) bu kategorideki yontemlerdendir.

Ornekler: Musteri segmentasyonu, anomali tespiti, oneri sistemleri.

### Pekistirmeli Ogrenme (Reinforcement Learning)
Pekistirmeli ogrenmede, bir ajan cevre ile etkilesime girerek odul ve ceza sinyalleri alir. Ajan, toplam odulu maksimize edecek stratejiyi ogrenir. Oyun yapay zekasi ve robotik alanlarda yaygin olarak kullanilir.

## Derin Ogrenme (Deep Learning)

Derin ogrenme, cok katmanli yapay sinir aglari kullanan makine ogrenimi yontemidir. Ozellikle goruntu tanima, dogal dil isleme ve konusma tanima alanlarinda buyuk basarilar elde etmistir.

Temel yapay sinir agi mimarileri sunlardir:
- CNN (Convolutional Neural Network): Goruntu isleme icin
- RNN (Recurrent Neural Network): Sirali veri isleme icin
- Transformer: Dogal dil isleme icin (GPT, BERT gibi modeller)

## Buyuk Dil Modelleri (LLM)

Buyuk dil modelleri, milyarlarca parametre ile egitilen transformer tabanli modellerdir. GPT, LLaMA, Phi ve Mistral gibi modeller, metin uretimi, cevirisi, ozetleme ve soru-cevap gibi gorevlerde ustun performans sergiler.

RAG (Retrieval-Augmented Generation) yaklasimi, bu modellerin bilgi tabanlarindan alinan verilerle zenginlestirilmesini saglar. Bu sayede model, kendi egitim verisinde olmayan guncel bilgilere de erisebilir ve daha dogru cevaplar uretebilir.

## Microsoft Foundry Local

Microsoft Foundry Local, yapay zeka modellerini tamamen yerel cihazda calistirmayi saglayan bir araçtır. Internet baglantisi gerektirmeden, kullanicinin bilgisayarinda LLM ve embedding modelleri calistirilabilir.

Foundry Local'in avantajlari:
- Gizlilik: Veriler cihazdan cikmaz
- Hiz: Ag gecikmesi yoktur
- Cevrimdisi kullanim: Internet olmadan calisir
- Maliyet: Bulut API ucreti yoktur

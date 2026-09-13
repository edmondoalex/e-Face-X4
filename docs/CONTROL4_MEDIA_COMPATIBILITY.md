# Matrice di compatibilità media Control4

Obiettivo: supportare le diverse forme di metadati, icone e cover prodotte da Control4 e dalle sorgenti collegate senza aggiungere un'eccezione improvvisata per ogni brano. Ogni caso reale va registrato con un test di regressione e verificato nell'app installata.

| Caso osservato | Origine cover | Stato |
| --- | --- | --- |
| Radio RapTz su Sonos | `http://192.168.3.36:1400` | Cover e logo Sonos verificati in e-Face dopo la 2.20.59 |
| Sonos Radio, brano “Handle Me” | `https://sonosradio.imgix.net:443` | Blocco `415` identificato; regola per host pubblici introdotta nella 2.20.61; utente ha confermato la cover tornata |
| Audio Cast / Wireless Music Bridge / BubbleUPnP | `http://director:80` | Blocco `415` identificato; alias mappato al Director configurato nella 2.20.63; verifica sul dispositivo ancora da fare |
| Altri tre casi citati dall'utente, usati il giorno precedente | Origini e metadati da acquisire | **Da identificare**, non considerati verificati |

Per ogni nuovo caso registrare solo: sorgente Control4, tipo di URL (LAN IP, alias Director, dominio pubblico), schema, porta, HTTP status, MIME, dimensione, eventuale redirect e risultato visivo. Non salvare URL completi se contengono token, password o identificatori sensibili. Il link diagnostico admin è temporaneo e monouso.

## Regole di compatibilità

- Gli URL pubblici sono ammessi senza lista di CDN, purché risolvano a indirizzi Internet; i redirect sono ricontrollati a ogni passaggio.
- Gli URL LAN sono ammessi nella rete del Director o per IP aggiunti esplicitamente dall'admin; porte privilegiate diverse da 80/443 restano bloccate.
- L'alias esatto `director` su HTTP/80 viene tradotto all'IP Director configurato. Non equivale ad accettare nomi interni arbitrari.
- Cover e logo sorgente sono distinti: la cover descrive il contenuto, il badge deve mostrare l'apparato attivo.
- Gli errori non vanno nascosti con un'immagine di default quando la diagnostica può identificare un'incompatibilità reale.

## Criteri per dichiarare una sorgente compatibile

1. Diagnosi: richiesta riuscita con status 200, MIME immagine e dimensione accettata; se manca un URL originale, è previsto un fallback visivo esplicito.
2. Interfaccia: cover e logo corretti in e-Face su desktop e Android, anche dopo cambio brano, cambio sorgente e riavvio dell'add-on.
3. Test: fixture per il tipo di URL/redirect e per il fallimento che lo aveva rivelato.
4. Sicurezza: nessun URL della cover permette accesso arbitrario a servizi interni o esposizione di segreti.

La compatibilità totale Control4 resta un task aperto: si chiude solo dopo inventario delle sorgenti reali dell'impianto e test sui loro media, non dopo il solo caso “Audio Cast”.

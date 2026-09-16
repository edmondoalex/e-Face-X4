# Regola permanente: volume master proporzionale

Il volume generale di una sessione multiroom e-Face applica esclusivamente la variazione relativa a ciascuna stanza.

- Esempio obbligatorio: Ufficio 40%, Contabilità 50%, master +10 punti => Ufficio 50%, Contabilità 60%.
- È vietato inviare lo stesso valore assoluto a tutti i membri del gruppo.
- Con WiiM collegato a Control4, WiiM fornisce metadati e trasporto; volume e mute restano quelli individuali delle stanze Control4.
- Il WiiM standalone usa invece direttamente volume e mute del dispositivo WiiM.

Ogni modifica a sessioni, gruppi, integrazione WiiM o overlay media deve conservare questa regola e superare i test di regressione dedicati.

# Varsel: «Nytt i sakene du følger»

E-posten til dem som følger saker (ADR-027) sendes av edge-funksjonen
`varsel`, ikke av Supabase Auth. Malen ligger derfor i
`supabase/functions/varsel/mal.ts`: funksjonen får bare med filene i sin egen
mappe. Malene her limes inn i Supabase for hånd og gjelder innloggingen.

Prøv malen med `node --test supabase/functions/varsel/logikk.test.ts`.

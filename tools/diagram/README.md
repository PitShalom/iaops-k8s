# Diagrama de arquitetura animado

`arquitetura.html` é um SVG animado por tempo determinístico (`renderAt(t)`);
`render.mjs` captura os quadros com o Chrome instalado e gera o GIF e o PNG.

```bash
cd tools/diagram
npm install
# CHROME_PATH opcional; padrão: C:\Program Files\Google\Chrome\Application\chrome.exe
npm run render        # grava docs/img/arquitetura.gif e arquitetura.png
```

package pl.latex.oferty;

import android.app.Activity;
import android.content.ClipData;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.print.PdfZapis;
import android.print.PrintAttributes;
import android.print.PrintDocumentAdapter;
import java.io.File;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Iterator;

/** Okno aplikacji: strona z assets/www w WebView + most "Native" (HTTP bez CORS, udostępnianie, linki, wersja). */
public class MainActivity extends Activity {
    private WebView web;
    private WebView pdfWeb;   // ukryta strona do wydruku PDF (pole, żeby nie zniknęła w trakcie)

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        getWindow().setStatusBarColor(Color.WHITE);
        getWindow().getDecorView().setSystemUiVisibility(android.view.View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR);
        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(false);
        s.setTextZoom(100);
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                String u = r.getUrl().toString();
                if (u.startsWith("file:///android_asset/")) return false;
                openExternal(u);
                return true;
            }
        });
        web.addJavascriptInterface(new Bridge(), "Native");
        if (b != null) web.restoreState(b); else web.loadUrl("file:///android_asset/www/index.html");
        setContentView(web);
    }

    @Override protected void onSaveInstanceState(Bundle o) { super.onSaveInstanceState(o); web.saveState(o); }

    @Override
    public void onBackPressed() {
        web.evaluateJavascript("window.onBack?window.onBack():false", new android.webkit.ValueCallback<String>() {
            public void onReceiveValue(String v) { if (!"true".equals(v)) finish(); } });
    }

    private void pdfWynik(boolean ok, String msg) {
        final String js = "window.__pdfDone&&window.__pdfDone(" + ok + "," + JSONObject.quote(msg) + ")";
        runOnUiThread(new Runnable() { public void run() { web.evaluateJavascript(js, null); } });
    }

    /** HTML oferty -> PDF A4 w cache/pdf -> okno „Udostępnij” (Gmail, WhatsApp, Dysk…). */
    private void zrobPdf(String html, String nazwa) {
        final File dir = new File(getCacheDir(), "pdf");
        dir.mkdirs();
        File[] stare = dir.listFiles();
        if (stare != null) for (File f : stare) if (f.lastModified() < System.currentTimeMillis() - 86400000L) f.delete();
        String n = nazwa == null ? "" : nazwa.replaceAll("[^0-9A-Za-z._-]+", "_").replaceAll("^_+|_+$", "");
        if (n.isEmpty()) n = "Oferta";
        final File out = new File(dir, (n.length() > 90 ? n.substring(0, 90) : n) + ".pdf");
        pdfWeb = new WebView(this);
        pdfWeb.getSettings().setJavaScriptEnabled(false);
        pdfWeb.getSettings().setAllowFileAccess(true);
        pdfWeb.setWebViewClient(new WebViewClient() {
            private boolean raz = false;
            @Override public void onPageFinished(WebView v, String url) {
                if (raz) return;
                raz = true;
                PrintDocumentAdapter a = v.createPrintDocumentAdapter(out.getName());
                PrintAttributes attrs = new PrintAttributes.Builder().setMediaSize(PrintAttributes.MediaSize.ISO_A4)
                    .setResolution(new PrintAttributes.Resolution("pdf", "pdf", 600, 600))
                    .setMinMargins(PrintAttributes.Margins.NO_MARGINS).setColorMode(PrintAttributes.COLOR_MODE_COLOR).build();
                PdfZapis.zapisz(a, attrs, out, new PdfZapis.Wynik() {
                    public void gotowe(boolean ok, String blad) {
                        pdfWeb = null;
                        if (!ok || !out.isFile()) { pdfWynik(false, "Nie udało się utworzyć PDF: " + blad); return; }
                        pdfWynik(true, out.getName());   // aplikacja pyta: Otwórz / Wyślij
                    }
                });
            }
            @Override public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) { return true; }
        });
        pdfWeb.loadDataWithBaseURL("file:///android_asset/www/", html, "text/html", "utf-8", null);
    }

    private void udostepnij(File f) {
        Uri u = Pliki.uri(f);
        Intent i = new Intent(Intent.ACTION_SEND);
        i.setType("application/pdf");
        i.putExtra(Intent.EXTRA_STREAM, u);
        i.putExtra(Intent.EXTRA_SUBJECT, "Oferta – opony");
        i.setClipData(ClipData.newRawUri("", u));
        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        startActivity(Intent.createChooser(i, "Wyślij PDF oferty"));
    }

    /** Plik PDF oferty z cache/pdf po nazwie (tylko .pdf, bez ścieżek). */
    private File plikPdf(String nazwa) {
        if (nazwa == null || nazwa.contains("/") || nazwa.contains("..") || !nazwa.endsWith(".pdf")) return null;
        File f = new File(new File(getCacheDir(), "pdf"), nazwa);
        return f.isFile() ? f : null;
    }

    /** Podgląd PDF w przeglądarce PDF telefonu (bez wysyłania) – tylko odczyt, jednorazowe pozwolenie. */
    private void otworz(File f) {
        Uri u = Pliki.uri(f);
        Intent i = new Intent(Intent.ACTION_VIEW);
        i.setDataAndType(u, "application/pdf");
        i.setClipData(ClipData.newRawUri("", u));
        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        try { startActivity(Intent.createChooser(i, "Otwórz PDF oferty")); }
        catch (Exception e) { pdfWynik(false, "Brak aplikacji do otwierania PDF – zainstaluj np. Dysk Google albo Adobe Acrobat."); }
    }

    private void openExternal(String u) {
        if (!u.startsWith("https://")) return;
        try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(u))); } catch (Exception e) { /* brak przeglądarki */ }
    }

    class Bridge {
        @JavascriptInterface
        public void http(final String id, final String method, final String url, final String headersJson, final String body) {
            new Thread(new Runnable() { public void run() {
                int status = 0; String text = "";
                try {
                    if (!url.startsWith("https://")) throw new Exception("tylko https");
                    HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
                    c.setConnectTimeout(20000); c.setReadTimeout(60000);
                    c.setRequestMethod(method);
                    JSONObject h = new JSONObject(headersJson == null || headersJson.isEmpty() ? "{}" : headersJson);
                    for (Iterator<String> it = h.keys(); it.hasNext(); ) { String k = it.next(); c.setRequestProperty(k, h.getString(k)); }
                    if (body != null && !body.isEmpty() && !"GET".equals(method)) {
                        c.setDoOutput(true);
                        try (OutputStream os = c.getOutputStream()) { os.write(body.getBytes("UTF-8")); }
                    }
                    status = c.getResponseCode();
                    InputStream in = status >= 400 ? c.getErrorStream() : c.getInputStream();
                    if (in != null) {
                        ByteArrayOutputStream bo = new ByteArrayOutputStream(); byte[] buf = new byte[16384]; int n;
                        while ((n = in.read(buf)) > 0) bo.write(buf, 0, n);
                        in.close(); text = bo.toString("UTF-8");
                    }
                    c.disconnect();
                } catch (Exception e) { status = 0; text = ""; }
                final String js = "window.__httpDone(" + JSONObject.quote(id) + "," + status + "," + JSONObject.quote(text) + ")";
                runOnUiThread(new Runnable() { public void run() { web.evaluateJavascript(js, null); } });
            } }).start();
        }

        @JavascriptInterface
        public void share(String text, String title) {
            final Intent i = new Intent(Intent.ACTION_SEND);
            i.setType("text/plain");
            i.putExtra(Intent.EXTRA_SUBJECT, title);
            i.putExtra(Intent.EXTRA_TEXT, text);
            runOnUiThread(new Runnable() { public void run() { startActivity(Intent.createChooser(i, "Wyślij ofertę")); } });
        }

        @JavascriptInterface
        public void pdf(final String html, final String nazwa) {
            runOnUiThread(new Runnable() { public void run() { zrobPdf(html, nazwa); } });
        }

        @JavascriptInterface
        public void pdfOtworz(final String nazwa) {
            runOnUiThread(new Runnable() { public void run() { File f = plikPdf(nazwa); if (f != null) otworz(f); } });
        }

        @JavascriptInterface
        public void pdfWyslij(final String nazwa) {
            runOnUiThread(new Runnable() { public void run() { File f = plikPdf(nazwa); if (f != null) udostepnij(f); } });
        }

        @JavascriptInterface
        public void openUrl(final String u) { runOnUiThread(new Runnable() { public void run() { openExternal(u); } }); }

        @JavascriptInterface
        public String version() {
            try { PackageInfo p = getPackageManager().getPackageInfo(getPackageName(), 0); return p.versionName; } catch (Exception e) { return "?"; }
        }
    }
}

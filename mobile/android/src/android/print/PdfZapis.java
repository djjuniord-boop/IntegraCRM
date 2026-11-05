package android.print;

import android.os.CancellationSignal;
import android.os.ParcelFileDescriptor;
import java.io.File;

/** Zapis strony WebView do pliku PDF bez okna drukowania. Klasa w pakiecie android.print, bo wywołania zwrotne
 *  LayoutResultCallback/WriteResultCallback mają konstruktory widoczne tylko w tym pakiecie (znany, stabilny sposób). */
public class PdfZapis {
    public interface Wynik { void gotowe(boolean ok, String blad); }

    public static void zapisz(final PrintDocumentAdapter a, final PrintAttributes attrs, final File out, final Wynik w) {
        a.onStart();
        a.onLayout(null, attrs, new CancellationSignal(), new PrintDocumentAdapter.LayoutResultCallback() {
            @Override public void onLayoutFinished(PrintDocumentInfo info, boolean changed) {
                try {
                    final ParcelFileDescriptor fd = ParcelFileDescriptor.open(out,
                        ParcelFileDescriptor.MODE_READ_WRITE | ParcelFileDescriptor.MODE_CREATE | ParcelFileDescriptor.MODE_TRUNCATE);
                    a.onWrite(new PageRange[]{PageRange.ALL_PAGES}, fd, new CancellationSignal(), new PrintDocumentAdapter.WriteResultCallback() {
                        @Override public void onWriteFinished(PageRange[] pages) { zamknij(fd); a.onFinish(); w.gotowe(true, ""); }
                        @Override public void onWriteFailed(CharSequence e) { zamknij(fd); a.onFinish(); w.gotowe(false, String.valueOf(e)); }
                        @Override public void onWriteCancelled() { zamknij(fd); a.onFinish(); w.gotowe(false, "przerwano"); }
                    });
                } catch (Exception e) { a.onFinish(); w.gotowe(false, e.toString()); }
            }
            @Override public void onLayoutFailed(CharSequence e) { a.onFinish(); w.gotowe(false, String.valueOf(e)); }
        }, null);
    }

    private static void zamknij(ParcelFileDescriptor fd) { try { fd.close(); } catch (Exception e) { /* nic */ } }
}

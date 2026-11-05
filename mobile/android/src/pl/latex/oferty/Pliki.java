package pl.latex.oferty;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import java.io.File;
import java.io.FileNotFoundException;

/** Udostępnia innym aplikacjom (Gmail, WhatsApp…) tylko pliki PDF ofert z cache/pdf – tylko do odczytu,
 *  tylko z jednorazowym pozwoleniem nadanym w Intencie (provider nie jest eksportowany). */
public class Pliki extends ContentProvider {
    static final String AUTH = "pl.latex.oferty.pliki";

    static Uri uri(File f) { return Uri.parse("content://" + AUTH + "/pdf/" + Uri.encode(f.getName())); }

    private File plik(Uri u) throws FileNotFoundException {
        String n = u.getLastPathSegment();
        if (n == null || n.contains("/") || n.contains("..") || !n.endsWith(".pdf")) throw new FileNotFoundException();
        File f = new File(new File(getContext().getCacheDir(), "pdf"), n);
        if (!f.isFile()) throw new FileNotFoundException();
        return f;
    }

    @Override public boolean onCreate() { return true; }
    @Override public String getType(Uri u) { return "application/pdf"; }
    @Override public ParcelFileDescriptor openFile(Uri u, String mode) throws FileNotFoundException {
        return ParcelFileDescriptor.open(plik(u), ParcelFileDescriptor.MODE_READ_ONLY);
    }
    @Override public Cursor query(Uri u, String[] proj, String sel, String[] args, String sort) {
        try {
            File f = plik(u);
            MatrixCursor c = new MatrixCursor(new String[]{OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE});
            c.addRow(new Object[]{f.getName(), f.length()});
            return c;
        } catch (FileNotFoundException e) { return null; }
    }
    @Override public Uri insert(Uri u, ContentValues v) { return null; }
    @Override public int delete(Uri u, String s, String[] a) { return 0; }
    @Override public int update(Uri u, ContentValues v, String s, String[] a) { return 0; }
}

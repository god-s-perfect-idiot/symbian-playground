"""Minimal Symbian^3 GUI hello sources for gnupoc/abld."""

from __future__ import annotations

from pathlib import Path


def write_native_app(root: Path, name: str, uid: str, title: str) -> None:
    uid_num = uid.lower().replace("0x", "")
    group = root / "group"
    src = root / "src"
    data = root / "data"
    pkg = root / "pkg"
    sis = root / "sis"
    for d in (group, src, data, pkg, sis):
        d.mkdir(parents=True, exist_ok=True)

    (group / "bld.inf").write_text(
        f"""PRJ_PLATFORMS
GCCE

PRJ_MMPFILES
{name}.mmp
""",
        encoding="utf-8",
    )

    (group / f"{name}.mmp").write_text(
        f"""TARGET          {name}.exe
TARGETTYPE      exe
UID             0x100039CE 0x{uid_num}

CAPABILITY      NONE
VENDORID        0

SOURCEPATH      ../src
SOURCE          main.cpp

USERINCLUDE     ../src
SYSTEMINCLUDE   \\epoc32\\include
SYSTEMINCLUDE   \\epoc32\\include\\mw
SYSTEMINCLUDE   \\epoc32\\include\\platform
SYSTEMINCLUDE   \\epoc32\\include\\platform\\mw
SYSTEMINCLUDE   \\epoc32\\include\\app
SYSTEMINCLUDE   \\epoc32\\include\\stdapis

LIBRARY         euser.lib efsrv.lib estor.lib
LIBRARY         cone.lib eikcore.lib avkon.lib
LIBRARY         gdi.lib apparc.lib eikcoctl.lib
LIBRARY         bafl.lib egul.lib fbscli.lib bitgdi.lib

START RESOURCE ../data/{name}.rss
HEADER
TARGETPATH      \\resource\\apps
END

START RESOURCE ../data/{name}_reg.rss
TARGETPATH      \\private\\10003a3f\\apps
END
""",
        encoding="utf-8",
    )

    (src / "main.cpp").write_text(
        f"""// Minimal Symbian^3 console-style UI app for harness testing.
#include <e32base.h>
#include <e32std.h>
#include <eikenv.h>
#include <aknutils.h>
#include <coemain.h>
#include <eikappui.h>
#include <eikapp.h>
#include <eikdoc.h>
#include <aknapp.h>
#include <akndoc.h>
#include <aknappui.h>
#include <e32debug.h>

_LIT(KTitle, "{title}");
_LIT(KHello, "Hello from SIS / sym harness");

class CHelloAppUi;
class CHelloDocument;
class CHelloApplication;

class CHelloApplication : public CAknApplication
{{
private:
    CApaDocument* CreateDocumentL();
    TUid AppDllUid() const;
}};

class CHelloDocument : public CAknDocument
{{
public:
    CHelloDocument(CEikApplication& aApp) : CAknDocument(aApp) {{}}
private:
    CEikAppUi* CreateAppUiL();
}};

class CHelloAppUi : public CAknAppUi
{{
public:
    void ConstructL();
    ~CHelloAppUi();
private:
    void HandleCommandL(TInt aCommand);
}};

TUid CHelloApplication::AppDllUid() const
{{
    return TUid::Uid(0x{uid_num});
}}

CApaDocument* CHelloApplication::CreateDocumentL()
{{
    return new (ELeave) CHelloDocument(*this);
}}

CEikAppUi* CHelloDocument::CreateAppUiL()
{{
    return new (ELeave) CHelloAppUi;
}}

void CHelloAppUi::ConstructL()
{{
    BaseConstructL(EAknEnableSkin);
    RDebug::Print(_L("sym:{name}: %S"), &KHello);
    // Auto-exit after construct so install smoke-tests don't hang a UI loop forever
    // when run under automation. Comment out Exit() for interactive use.
    // Exit();
}}

CHelloAppUi::~CHelloAppUi() {{}}

void CHelloAppUi::HandleCommandL(TInt aCommand)
{{
    if (aCommand == EEikCmdExit || aCommand == EAknSoftkeyExit)
        Exit();
}}

LOCAL_C CApaApplication* NewApplication()
{{
    return new CHelloApplication;
}}

GLDEF_C TInt E32Main()
{{
    return EikStart::RunApplication(NewApplication);
}}
""",
        encoding="utf-8",
    )

    # Need eikstart
    # Fix include - EikStart is in eikstart.h / library eikcore
    text = (src / "main.cpp").read_text(encoding="utf-8")
    text = text.replace(
        "#include <e32debug.h>",
        "#include <e32debug.h>\n#include <eikstart.h>",
    )
    (src / "main.cpp").write_text(text, encoding="utf-8")

    (data / f"{name}.rss").write_text(
        f"""NAME HELO
#include <avkon.rsg>
#include <avkon.rh>
#include <eikon.rh>
#include <appinfo.rh>
#include "{name}.hrh"

RESOURCE RSS_SIGNATURE {{ }}

RESOURCE TBUF {{ buf = "{title}"; }}

RESOURCE EIK_APP_INFO
{{
    menubar = r_hello_menubar;
    cba = R_AVKON_SOFTKEYS_OPTIONS_EXIT;
}}

RESOURCE MENU_BAR r_hello_menubar
{{
    titles =
    {{
        MENU_TITLE {{ menu_pane = r_hello_menu; }}
    }};
}}

RESOURCE MENU_PANE r_hello_menu
{{
    items =
    {{
        MENU_ITEM {{ command = EAknSoftkeyExit; txt = "Exit"; }}
    }};
}}
""",
        encoding="utf-8",
    )

    (data / f"{name}.hrh").write_text(
        """enum THelloCommands
{
    EHelloDummy = 0x1000
};
""",
        encoding="utf-8",
    )

    (data / f"{name}_reg.rss").write_text(
        f"""#include <appinfo.rh>

UID2 KUidAppRegistrationResourceFile
UID3 0x{uid_num}

RESOURCE APP_REGISTRATION_INFO
{{
    app_file = "{name}";
    localisable_resource_file = "\\\\resource\\\\apps\\\\{name}";
}}
""",
        encoding="utf-8",
    )

    # PKG — paths relative to EPOCROOT via makesis -d
    (pkg / f"{name}.pkg").write_text(
        f"""; {title}
&EN
#{{"{title}"}},(0x{uid_num}),1,0,0,TYPE=SA
%{{"SymDev"}}
:"{title}"
"epoc32\\release\\gcce\\urel\\{name}.exe"-"!:\\sys\\bin\\{name}.exe"
"epoc32\\data\\z\\resource\\apps\\{name}.rsc"-"!:\\resource\\apps\\{name}.rsc"
"epoc32\\data\\z\\private\\10003a3f\\apps\\{name}_reg.rsc"-"!:\\private\\10003a3f\\import\\apps\\{name}_reg.rsc"
""",
        encoding="utf-8",
    )

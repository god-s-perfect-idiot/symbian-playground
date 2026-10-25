// Minimal Symbian^3 console-style UI app for harness testing.
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
#include <eikstart.h>

_LIT(KTitle, "Hello SIS");
_LIT(KHello, "Hello from SIS / sym harness");

class CHelloAppUi;
class CHelloDocument;
class CHelloApplication;

class CHelloApplication : public CAknApplication
{
private:
    CApaDocument* CreateDocumentL();
    TUid AppDllUid() const;
};

class CHelloDocument : public CAknDocument
{
public:
    CHelloDocument(CEikApplication& aApp) : CAknDocument(aApp) {}
private:
    CEikAppUi* CreateAppUiL();
};

class CHelloAppUi : public CAknAppUi
{
public:
    void ConstructL();
    ~CHelloAppUi();
private:
    void HandleCommandL(TInt aCommand);
};

TUid CHelloApplication::AppDllUid() const
{
    return TUid::Uid(0xea9dceac);
}

CApaDocument* CHelloApplication::CreateDocumentL()
{
    return new (ELeave) CHelloDocument(*this);
}

CEikAppUi* CHelloDocument::CreateAppUiL()
{
    return new (ELeave) CHelloAppUi;
}

void CHelloAppUi::ConstructL()
{
    BaseConstructL(EAknEnableSkin);
    RDebug::Print(_L("sym:hello_sis: %S"), &KHello);
    // Auto-exit after construct so install smoke-tests don't hang a UI loop forever
    // when run under automation. Comment out Exit() for interactive use.
    // Exit();
}

CHelloAppUi::~CHelloAppUi() {}

void CHelloAppUi::HandleCommandL(TInt aCommand)
{
    if (aCommand == EEikCmdExit || aCommand == EAknSoftkeyExit)
        Exit();
}

LOCAL_C CApaApplication* NewApplication()
{
    return new CHelloApplication;
}

GLDEF_C TInt E32Main()
{
    return EikStart::RunApplication(NewApplication);
}

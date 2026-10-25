// Pomodoro timer for Symbian^3 — set minutes, countdown, beep when done.
#include <e32base.h>
#include <e32std.h>
#include <eikenv.h>
#include <aknutils.h>
#include <coemain.h>
#include <coecntrl.h>
#include <eikappui.h>
#include <eikapp.h>
#include <eikdoc.h>
#include <aknapp.h>
#include <akndoc.h>
#include <aknappui.h>
#include <e32debug.h>
#include <eikstart.h>
#include <eikbtgpc.h>
#include <gdi.h>
#include <aknnotewrappers.h>

#include <pomodoro.rsg>
#include "pomodoro.hrh"

_LIT(KTitle, "Pomodoro");
_LIT(KRunning, "Focus - time left");
_LIT(KDone, "Done! Take a break");
_LIT(KStartLbl, "Start");
_LIT(KStopLbl, "Stop");

const TInt KDefaultMinutes = 25;
const TInt KMinMinutes = 1;
const TInt KMaxMinutes = 99;
const TInt KTickUs = 1000000; // 1 second

class CPomoContainer;
class CPomoAppUi;
class CPomoDocument;
class CPomoApplication;

class CPomoApplication : public CAknApplication
{
private:
    CApaDocument* CreateDocumentL();
    TUid AppDllUid() const;
};

class CPomoDocument : public CAknDocument
{
public:
    CPomoDocument(CEikApplication& aApp) : CAknDocument(aApp) {}
private:
    CEikAppUi* CreateAppUiL();
};

class CPomoContainer : public CCoeControl
{
public:
    static CPomoContainer* NewL(const TRect& aRect);
    ~CPomoContainer();

    void SetMinutes(TInt aMinutes);
    void SetRemaining(TInt aSeconds);
    void SetRunning(TBool aRunning);
    void SetFinished(TBool aFinished);
    void Draw(const TRect& aRect) const;

private:
    void ConstructL(const TRect& aRect);
    void SizeChanged();

    TInt iMinutes;
    TInt iRemainSec;
    TBool iRunning;
    TBool iFinished;
};

class CPomoAppUi : public CAknAppUi
{
public:
    void ConstructL();
    ~CPomoAppUi();

private:
    void HandleCommandL(TInt aCommand);
    void HandleResourceChangeL(TInt aType);
    void HandleStatusPaneSizeChange();

    void StartTimerL();
    void StopTimer();
    void ResetIdle();
    void SetPreset(TInt aMinutes);
    void AdjustMinutes(TInt aDelta);
    void UpdateSoftkeys();
    void RefreshView();
    void BeepDone();
    static TInt TickCallback(TAny* aPtr);
    void OnTick();

    CPomoContainer* iContainer;
    CPeriodic* iTicker;
    TInt iSetMinutes;
    TInt iRemainSec;
    TBool iRunning;
};

TUid CPomoApplication::AppDllUid() const
{
    return TUid::Uid(0xe73f6135);
}

CApaDocument* CPomoApplication::CreateDocumentL()
{
    return new (ELeave) CPomoDocument(*this);
}

CEikAppUi* CPomoDocument::CreateAppUiL()
{
    return new (ELeave) CPomoAppUi;
}

// --- Container ----------------------------------------------------------------

CPomoContainer* CPomoContainer::NewL(const TRect& aRect)
{
    CPomoContainer* self = new (ELeave) CPomoContainer;
    CleanupStack::PushL(self);
    self->ConstructL(aRect);
    CleanupStack::Pop(self);
    return self;
}

void CPomoContainer::ConstructL(const TRect& aRect)
{
    iMinutes = KDefaultMinutes;
    iRemainSec = KDefaultMinutes * 60;
    iRunning = EFalse;
    iFinished = EFalse;
    CreateWindowL();
    SetRect(aRect);
    ActivateL();
}

CPomoContainer::~CPomoContainer() {}

void CPomoContainer::SizeChanged() {}

void CPomoContainer::SetMinutes(TInt aMinutes)
{
    iMinutes = aMinutes;
    if (!iRunning && !iFinished)
        iRemainSec = aMinutes * 60;
    DrawNow();
}

void CPomoContainer::SetRemaining(TInt aSeconds)
{
    iRemainSec = aSeconds;
    DrawNow();
}

void CPomoContainer::SetRunning(TBool aRunning)
{
    iRunning = aRunning;
    if (aRunning)
        iFinished = EFalse;
    DrawNow();
}

void CPomoContainer::SetFinished(TBool aFinished)
{
    iFinished = aFinished;
    DrawNow();
}

void CPomoContainer::Draw(const TRect& /*aRect*/) const
{
    CWindowGc& gc = SystemGc();
    TRect r = Rect();
    gc.SetBrushStyle(CGraphicsContext::ESolidBrush);
    gc.SetBrushColor(KRgbBlack);
    gc.SetPenStyle(CGraphicsContext::ENullPen);
    gc.DrawRect(r);

    gc.SetPenStyle(CGraphicsContext::ESolidPen);
    gc.SetPenColor(KRgbWhite);
    gc.SetBrushStyle(CGraphicsContext::ENullBrush);

    const CFont* titleFont = AknLayoutUtils::FontFromId(EAknLogicalFontPrimaryFont);
    const CFont* bigFont = AknLayoutUtils::FontFromId(EAknLogicalFontTitleFont);
    const CFont* smallFont = AknLayoutUtils::FontFromId(EAknLogicalFontSecondaryFont);

    gc.UseFont(titleFont);
    TInt y = r.iTl.iY + titleFont->HeightInPixels() + 8;
    gc.DrawText(KTitle, TPoint(r.iTl.iX + 12, y));
    gc.DiscardFont();

    TBuf<16> timeBuf;
    TInt sec = iRemainSec;
    if (sec < 0)
        sec = 0;
    timeBuf.Format(_L("%02d:%02d"), sec / 60, sec % 60);

    gc.UseFont(bigFont);
    TInt bigH = bigFont->HeightInPixels();
    TInt bigW = bigFont->TextWidthInPixels(timeBuf);
    TInt cx = (r.Width() - bigW) / 2;
    TInt cy = r.iTl.iY + r.Height() / 2 + bigH / 3;
    gc.SetPenColor(iFinished ? KRgbYellow : KRgbWhite);
    gc.DrawText(timeBuf, TPoint(r.iTl.iX + cx, cy));
    gc.DiscardFont();

    gc.UseFont(smallFont);
    gc.SetPenColor(KRgbGray);
    TBuf<48> hint;
    if (iFinished)
        hint.Copy(KDone);
    else if (iRunning)
        hint.Copy(KRunning);
    else
        hint.Format(_L("Ready: %d min - Options to set"), iMinutes);
    TInt hw = smallFont->TextWidthInPixels(hint);
    TInt hy = r.iBr.iY - 16;
    gc.DrawText(hint, TPoint(r.iTl.iX + (r.Width() - hw) / 2, hy));
    gc.DiscardFont();
}

// --- AppUi --------------------------------------------------------------------

void CPomoAppUi::ConstructL()
{
    BaseConstructL(EAknEnableSkin);
    iSetMinutes = KDefaultMinutes;
    iRemainSec = KDefaultMinutes * 60;
    iRunning = EFalse;
    iTicker = NULL;

    iContainer = CPomoContainer::NewL(ClientRect());
    AddToStackL(iContainer);
    UpdateSoftkeys();
    RefreshView();
}

CPomoAppUi::~CPomoAppUi()
{
    StopTimer();
    if (iContainer)
    {
        RemoveFromStack(iContainer);
        delete iContainer;
    }
}

void CPomoAppUi::HandleResourceChangeL(TInt aType)
{
    CAknAppUi::HandleResourceChangeL(aType);
    if (aType == KEikDynamicLayoutVariantSwitch && iContainer)
        iContainer->SetRect(ClientRect());
}

void CPomoAppUi::HandleStatusPaneSizeChange()
{
    if (iContainer)
        iContainer->SetRect(ClientRect());
}

void CPomoAppUi::UpdateSoftkeys()
{
    CEikButtonGroupContainer* cba = Cba();
    if (!cba)
        return;
    if (iRunning)
        cba->SetCommandL(0, ECmdStartStop, KStopLbl);
    else
        cba->SetCommandL(0, ECmdStartStop, KStartLbl);
    cba->DrawNow();
}

void CPomoAppUi::RefreshView()
{
    if (!iContainer)
        return;
    iContainer->SetMinutes(iSetMinutes);
    iContainer->SetRemaining(iRemainSec);
    iContainer->SetRunning(iRunning);
}

void CPomoAppUi::StartTimerL()
{
    if (iRunning)
        return;
    if (iRemainSec <= 0)
        iRemainSec = iSetMinutes * 60;
    if (!iTicker)
        iTicker = CPeriodic::NewL(CActive::EPriorityStandard);
    iTicker->Cancel();
    iTicker->Start(KTickUs, KTickUs, TCallBack(TickCallback, this));
    iRunning = ETrue;
    if (iContainer)
        iContainer->SetFinished(EFalse);
    UpdateSoftkeys();
    RefreshView();
}

void CPomoAppUi::StopTimer()
{
    if (iTicker)
    {
        iTicker->Cancel();
        delete iTicker;
        iTicker = NULL;
    }
    iRunning = EFalse;
    UpdateSoftkeys();
    RefreshView();
}

void CPomoAppUi::ResetIdle()
{
    StopTimer();
    iRemainSec = iSetMinutes * 60;
    if (iContainer)
        iContainer->SetFinished(EFalse);
    RefreshView();
}

void CPomoAppUi::SetPreset(TInt aMinutes)
{
    if (iRunning)
        return;
    if (aMinutes < KMinMinutes)
        aMinutes = KMinMinutes;
    if (aMinutes > KMaxMinutes)
        aMinutes = KMaxMinutes;
    iSetMinutes = aMinutes;
    iRemainSec = iSetMinutes * 60;
    if (iContainer)
        iContainer->SetFinished(EFalse);
    RefreshView();
}

void CPomoAppUi::AdjustMinutes(TInt aDelta)
{
    if (iRunning)
        return;
    SetPreset(iSetMinutes + aDelta);
}

void CPomoAppUi::BeepDone()
{
    // Three short system beeps
    User::Beep(880, 200000);
    User::After(250000);
    User::Beep(988, 200000);
    User::After(250000);
    User::Beep(1175, 400000);

    TRAP_IGNORE(
        {
            CAknInformationNote* note = new (ELeave) CAknInformationNote(ETrue);
            note->ExecuteLD(KDone);
        });
}

TInt CPomoAppUi::TickCallback(TAny* aPtr)
{
    static_cast<CPomoAppUi*>(aPtr)->OnTick();
    return 0;
}

void CPomoAppUi::OnTick()
{
    if (!iRunning)
        return;
    if (iRemainSec > 0)
        --iRemainSec;
    RefreshView();
    if (iRemainSec <= 0)
    {
        StopTimer();
        iRemainSec = 0;
        if (iContainer)
            iContainer->SetFinished(ETrue);
        RefreshView();
        BeepDone();
    }
}

void CPomoAppUi::HandleCommandL(TInt aCommand)
{
    switch (aCommand)
    {
    case ECmdStartStop:
        if (iRunning)
            StopTimer();
        else
            StartTimerL();
        break;
    case ECmdPlusMin:
        AdjustMinutes(1);
        break;
    case ECmdMinusMin:
        AdjustMinutes(-1);
        break;
    case ECmdSet5:
        SetPreset(5);
        break;
    case ECmdSet15:
        SetPreset(15);
        break;
    case ECmdSet25:
        SetPreset(25);
        break;
    case ECmdSet45:
        SetPreset(45);
        break;
    case ECmdReset:
        ResetIdle();
        break;
    case EEikCmdExit:
    case EAknSoftkeyExit:
        Exit();
        break;
    default:
        break;
    }
}

LOCAL_C CApaApplication* NewApplication()
{
    return new CPomoApplication;
}

GLDEF_C TInt E32Main()
{
    return EikStart::RunApplication(NewApplication);
}

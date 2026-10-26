// Pomodoro timer — abstract flip-clock countdown for Symbian^3 / E7.
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
#include <w32std.h>

#include <pomodoro.rsg>
#include "pomodoro.hrh"

_LIT(KDoneNote, "Done! Take a break");
_LIT(KStartLbl, "Start");
_LIT(KStopLbl, "Stop");
_LIT(KAgainLbl, "Again");

const TInt KDefaultTotalSec = 25 * 60;
const TInt KMinTotalSec = 1;
const TInt KMaxTotalSec = 99 * 60 + 59;
const TInt KTickUs = 1000000;

const TRgb KBg(0x16, 0x14, 0x12);
const TRgb KPanel(0x22, 0x1e, 0x1c);
const TRgb KInk(0xf0, 0xeb, 0xe6);
const TRgb KMuted(0x9a, 0x8f, 0x86);
const TRgb KTileTop(0x35, 0x30, 0x2c);
const TRgb KTileBot(0x22, 0x1e, 0x1c);
const TRgb KAccent(0xc4, 0x4a, 0x3a);
const TRgb KDone(0xd4, 0xa8, 0x4a);
const TRgb KBarTrack(0x2e, 0x29, 0x26);
const TRgb KSeam(0x0a, 0x09, 0x08);
const TRgb KBtnFace(0x2a, 0x26, 0x24);
const TRgb KBtnEdge(0x3a, 0x34, 0x2f);

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
    static CPomoContainer* NewL(const TRect& aRect, CPomoAppUi& aUi);
    ~CPomoContainer();

    void SetState(TInt aSetTotalSec, TInt aRemainSec, TBool aRunning, TBool aFinished);
    void Draw(const TRect& aRect) const;
    void HandlePointerEventL(const TPointerEvent& aPointerEvent);

private:
    CPomoContainer(CPomoAppUi& aUi);
    void ConstructL(const TRect& aRect);
    void SizeChanged();
    void LayoutButtons();
    void DrawFlipDigit(CWindowGc& aGc, const TRect& aTile, TChar aDigit, TBool aDone) const;
    void DrawAdjButton(CWindowGc& aGc, const TRect& aBtn, const TDesC& aLabel) const;
    TInt HitAdjust(const TPoint& aPos) const; // returns ECmd* or 0

    CPomoAppUi& iUi;
    TInt iSetTotalSec;
    TInt iRemainSec;
    TBool iRunning;
    TBool iFinished;
    TRect iBtnMinMinus;
    TRect iBtnMinPlus;
    TRect iBtnSecMinus;
    TRect iBtnSecPlus;
    TRect iTiles[4];
    TInt iTileW;
    TInt iTileH;
    TInt iClockY;
};

class CPomoAppUi : public CAknAppUi
{
public:
    void ConstructL();
    ~CPomoAppUi();

    void AdjustMinutes(TInt aDelta);
    void AdjustSeconds(TInt aDelta);
    void HandleCommandL(TInt aCommand);

private:
    void HandleResourceChangeL(TInt aType);
    void HandleStatusPaneSizeChange();

    void StartTimerL();
    void StopTimer();
    void ResetIdle();
    void SetPresetMinutes(TInt aMinutes);
    void SetTotalSec(TInt aTotal);
    void UpdateSoftkeys();
    void RefreshView();
    void BeepDone();
    static TInt TickCallback(TAny* aPtr);
    void OnTick();

    CPomoContainer* iContainer;
    CPeriodic* iTicker;
    TInt iSetTotalSec;
    TInt iRemainSec;
    TBool iRunning;
    TBool iFinished;
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

CPomoContainer::CPomoContainer(CPomoAppUi& aUi) : iUi(aUi) {}

CPomoContainer* CPomoContainer::NewL(const TRect& aRect, CPomoAppUi& aUi)
{
    CPomoContainer* self = new (ELeave) CPomoContainer(aUi);
    CleanupStack::PushL(self);
    self->ConstructL(aRect);
    CleanupStack::Pop(self);
    return self;
}

void CPomoContainer::ConstructL(const TRect& aRect)
{
    iSetTotalSec = KDefaultTotalSec;
    iRemainSec = KDefaultTotalSec;
    iRunning = EFalse;
    iFinished = EFalse;
    CreateWindowL();
    EnableDragEvents();
    SetRect(aRect);
    ActivateL();
}

CPomoContainer::~CPomoContainer() {}

void CPomoContainer::SizeChanged()
{
    LayoutButtons();
}

void CPomoContainer::LayoutButtons()
{
    TRect r = Rect();
    // Large flip tiles for E7 landscape client area
    iTileH = Max(72, (r.Height() * 42) / 100);
    iTileW = Max(52, (iTileH * 3) / 4);
    if (iTileW > 78)
        iTileW = 78;
    if (iTileH > 110)
        iTileH = 110;

    const TInt gap = 4;
    const TInt colonGap = 10;
    const TInt pairGap = 8;
    const TInt btnW = 40;
    const TInt btnH = 40;
    const TInt btnGap = 6;
    const TInt totalClockW = iTileW * 4 + gap * 2 + colonGap + pairGap;
    const TInt rowW = btnW + btnGap + totalClockW + btnGap + btnW;
    // Actually layout: [btn][MM][btn] gap [btn][SS][btn]
    const TInt mmPairW = iTileW * 2 + gap;
    const TInt ssPairW = iTileW * 2 + gap;
    const TInt blockW = btnW + btnGap + mmPairW + btnGap + btnW
        + colonGap + pairGap
        + btnW + btnGap + ssPairW + btnGap + btnW;

    TInt x = r.iTl.iX + (r.Width() - blockW) / 2;
    iClockY = r.iTl.iY + 32 + (r.Height() - 32 - iTileH - 36) / 2;
    if (iClockY < r.iTl.iY + 32)
        iClockY = r.iTl.iY + 32;

    TInt yBtn = iClockY + (iTileH - btnH) / 2;

    iBtnMinMinus = TRect(TPoint(x, yBtn), TSize(btnW, btnH));
    x += btnW + btnGap;
    iTiles[0] = TRect(TPoint(x, iClockY), TSize(iTileW, iTileH));
    x += iTileW + gap;
    iTiles[1] = TRect(TPoint(x, iClockY), TSize(iTileW, iTileH));
    x += iTileW + btnGap;
    iBtnMinPlus = TRect(TPoint(x, yBtn), TSize(btnW, btnH));
    x += btnW + colonGap + pairGap;

    iBtnSecMinus = TRect(TPoint(x, yBtn), TSize(btnW, btnH));
    x += btnW + btnGap;
    iTiles[2] = TRect(TPoint(x, iClockY), TSize(iTileW, iTileH));
    x += iTileW + gap;
    iTiles[3] = TRect(TPoint(x, iClockY), TSize(iTileW, iTileH));
    x += iTileW + btnGap;
    iBtnSecPlus = TRect(TPoint(x, yBtn), TSize(btnW, btnH));
}

void CPomoContainer::SetState(TInt aSetTotalSec, TInt aRemainSec, TBool aRunning, TBool aFinished)
{
    iSetTotalSec = aSetTotalSec;
    iRemainSec = aRemainSec;
    iRunning = aRunning;
    iFinished = aFinished;
    DrawNow();
}

void CPomoContainer::DrawFlipDigit(CWindowGc& aGc, const TRect& aTile, TChar aDigit, TBool aDone) const
{
    const TInt mid = (aTile.iTl.iY + aTile.iBr.iY) / 2;
    TRect top(aTile.iTl, TPoint(aTile.iBr.iX, mid));
    TRect bot(TPoint(aTile.iTl.iX, mid), aTile.iBr);

    aGc.SetBrushStyle(CGraphicsContext::ESolidBrush);
    aGc.SetPenStyle(CGraphicsContext::ENullPen);
    aGc.SetBrushColor(KTileTop);
    aGc.DrawRect(top);
    aGc.SetBrushColor(KTileBot);
    aGc.DrawRect(bot);

    aGc.SetPenStyle(CGraphicsContext::ESolidPen);
    aGc.SetPenColor(KSeam);
    aGc.DrawLine(TPoint(aTile.iTl.iX, mid), TPoint(aTile.iBr.iX, mid));

    aGc.SetPenColor(aDone ? KDone : KInk);
    const CFont* font = CEikonEnv::Static()->TitleFont();
    aGc.UseFont(font);
    TBuf<1> ch;
    ch.Append(aDigit);
    TInt tw = font->TextWidthInPixels(ch);
    TInt th = font->HeightInPixels();
    TInt tx = aTile.iTl.iX + (aTile.Width() - tw) / 2;
    TInt ty = aTile.iTl.iY + (aTile.Height() + th) / 2 - font->DescentInPixels();
    aGc.DrawText(ch, TPoint(tx, ty));
    aGc.DiscardFont();
}

void CPomoContainer::DrawAdjButton(CWindowGc& aGc, const TRect& aBtn, const TDesC& aLabel) const
{
    aGc.SetBrushStyle(CGraphicsContext::ESolidBrush);
    aGc.SetPenStyle(CGraphicsContext::ESolidPen);
    aGc.SetPenColor(KBtnEdge);
    aGc.SetBrushColor(KBtnFace);
    aGc.DrawRect(aBtn);

    aGc.SetPenColor(KInk);
    const CFont* font = CEikonEnv::Static()->TitleFont();
    aGc.UseFont(font);
    TInt tw = font->TextWidthInPixels(aLabel);
    TInt th = font->HeightInPixels();
    TInt tx = aBtn.iTl.iX + (aBtn.Width() - tw) / 2;
    TInt ty = aBtn.iTl.iY + (aBtn.Height() + th) / 2 - font->DescentInPixels();
    aGc.DrawText(aLabel, TPoint(tx, ty));
    aGc.DiscardFont();
}

void CPomoContainer::Draw(const TRect& /*aRect*/) const
{
    CWindowGc& gc = SystemGc();
    TRect r = Rect();

    gc.SetBrushStyle(CGraphicsContext::ESolidBrush);
    gc.SetBrushColor(KBg);
    gc.SetPenStyle(CGraphicsContext::ENullPen);
    gc.DrawRect(r);

    TRect status(r.iTl, TSize(r.Width(), 28));
    gc.SetBrushColor(KPanel);
    gc.DrawRect(status);
    gc.SetBrushColor(KAccent);
    gc.DrawEllipse(TRect(status.iTl + TPoint(10, 9), TSize(10, 10)));
    gc.SetPenStyle(CGraphicsContext::ESolidPen);
    gc.SetPenColor(KInk);
    const CFont* statusFont = CEikonEnv::Static()->LegendFont();
    gc.UseFont(statusFont);
    gc.DrawText(_L("Pomodoro"), TPoint(status.iTl.iX + 28, status.iTl.iY + 19));
    gc.DiscardFont();

    TInt sec = iRemainSec;
    if (sec < 0)
        sec = 0;
    TInt mm = sec / 60;
    TInt ss = sec % 60;
    TBuf<4> digits;
    digits.Format(_L("%02d%02d"), mm, ss);

    // Use layout from SizeChanged; if empty (first paint), compute locally
    TRect tiles[4];
    TRect btnMM, btnMP, btnSM, btnSP;
    TInt tileH = iTileH;
    TInt clockY = iClockY;
    if (iTiles[0].Width() > 0)
    {
        for (TInt i = 0; i < 4; ++i)
            tiles[i] = iTiles[i];
        btnMM = iBtnMinMinus;
        btnMP = iBtnMinPlus;
        btnSM = iBtnSecMinus;
        btnSP = iBtnSecPlus;
    }
    else
    {
        // Fallback layout matching LayoutButtons defaults
        const_cast<CPomoContainer*>(this)->LayoutButtons();
        for (TInt i = 0; i < 4; ++i)
            tiles[i] = iTiles[i];
        btnMM = iBtnMinMinus;
        btnMP = iBtnMinPlus;
        btnSM = iBtnSecMinus;
        btnSP = iBtnSecPlus;
        tileH = iTileH;
        clockY = iClockY;
    }

    for (TInt i = 0; i < 4; ++i)
        DrawFlipDigit(gc, tiles[i], digits[i], iFinished);

    // Colon between minute and second pairs
    gc.SetBrushStyle(CGraphicsContext::ESolidBrush);
    gc.SetBrushColor(KMuted);
    gc.SetPenStyle(CGraphicsContext::ENullPen);
    TInt cx = (tiles[1].iBr.iX + tiles[2].iTl.iX) / 2 - 2;
    TInt cy = clockY + tileH / 2;
    gc.DrawRect(TRect(TPoint(cx, cy - 12), TSize(5, 5)));
    gc.DrawRect(TRect(TPoint(cx, cy + 8), TSize(5, 5)));

    // Adjust buttons when not running
    if (!iRunning)
    {
        DrawAdjButton(gc, btnMM, _L("-"));
        DrawAdjButton(gc, btnMP, _L("+"));
        DrawAdjButton(gc, btnSM, _L("-"));
        DrawAdjButton(gc, btnSP, _L("+"));
    }

    // Progress bar
    TInt total = iSetTotalSec;
    if (total < 1)
        total = 1;
    TInt barW = Min(280, r.Width() - 40);
    TInt barX = r.iTl.iX + (r.Width() - barW) / 2;
    TInt barY = clockY + tileH + 10;
    TRect track(TPoint(barX, barY), TSize(barW, 3));
    gc.SetBrushColor(KBarTrack);
    gc.SetPenStyle(CGraphicsContext::ENullPen);
    gc.DrawRect(track);
    TInt fillW = (barW * sec) / total;
    if (iFinished)
        fillW = 0;
    if (fillW > 0)
    {
        gc.SetBrushColor(iFinished ? KDone : KAccent);
        gc.DrawRect(TRect(TPoint(barX, barY), TSize(fillW, 3)));
    }

    const CFont* phaseFont = CEikonEnv::Static()->LegendFont();
    gc.UseFont(phaseFont);
    gc.SetPenStyle(CGraphicsContext::ESolidPen);
    gc.SetPenColor(KMuted);
    TBuf<48> phase;
    if (iFinished)
        phase.Format(_L("Done  -  take a break"));
    else if (iRunning)
        phase.Format(_L("Focus  -  time left"));
    else
        phase.Format(_L("Ready  -  set min / sec"));
    TInt pw = phaseFont->TextWidthInPixels(phase);
    gc.DrawText(phase, TPoint(r.iTl.iX + (r.Width() - pw) / 2, barY + 16));
    gc.DiscardFont();
}

TInt CPomoContainer::HitAdjust(const TPoint& aPos) const
{
    if (iRunning)
        return 0;
    if (iBtnMinMinus.Contains(aPos))
        return ECmdMinMinus;
    if (iBtnMinPlus.Contains(aPos))
        return ECmdMinPlus;
    if (iBtnSecMinus.Contains(aPos))
        return ECmdSecMinus;
    if (iBtnSecPlus.Contains(aPos))
        return ECmdSecPlus;
    return 0;
}

void CPomoContainer::HandlePointerEventL(const TPointerEvent& aPointerEvent)
{
    CCoeControl::HandlePointerEventL(aPointerEvent);
    if (aPointerEvent.iType != TPointerEvent::EButton1Up)
        return;
    TInt cmd = HitAdjust(aPointerEvent.iPosition);
    if (cmd)
        iUi.HandleCommandL(cmd);
}

// --- AppUi --------------------------------------------------------------------

void CPomoAppUi::ConstructL()
{
    BaseConstructL(EAknEnableSkin);
    iSetTotalSec = KDefaultTotalSec;
    iRemainSec = KDefaultTotalSec;
    iRunning = EFalse;
    iFinished = EFalse;
    iTicker = NULL;

    iContainer = CPomoContainer::NewL(ClientRect(), *this);
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
        cba->SetCommandL(0, EAknSoftkeyOk, KStopLbl);
    else if (iFinished)
        cba->SetCommandL(0, EAknSoftkeyOk, KAgainLbl);
    else
        cba->SetCommandL(0, EAknSoftkeyOk, KStartLbl);
    cba->DrawNow();
}

void CPomoAppUi::RefreshView()
{
    if (!iContainer)
        return;
    iContainer->SetState(iSetTotalSec, iRemainSec, iRunning, iFinished);
}

void CPomoAppUi::SetTotalSec(TInt aTotal)
{
    if (aTotal < KMinTotalSec)
        aTotal = KMinTotalSec;
    if (aTotal > KMaxTotalSec)
        aTotal = KMaxTotalSec;
    iSetTotalSec = aTotal;
    if (!iRunning)
    {
        iRemainSec = iSetTotalSec;
        iFinished = EFalse;
    }
    UpdateSoftkeys();
    RefreshView();
}

void CPomoAppUi::AdjustMinutes(TInt aDelta)
{
    if (iRunning)
        return;
    SetTotalSec(iSetTotalSec + aDelta * 60);
}

void CPomoAppUi::AdjustSeconds(TInt aDelta)
{
    if (iRunning)
        return;
    SetTotalSec(iSetTotalSec + aDelta);
}

void CPomoAppUi::StartTimerL()
{
    if (iRunning)
        return;
    if (iRemainSec <= 0 || iFinished)
    {
        iRemainSec = iSetTotalSec;
        iFinished = EFalse;
    }
    if (!iTicker)
        iTicker = CPeriodic::NewL(CActive::EPriorityStandard);
    iTicker->Cancel();
    iTicker->Start(KTickUs, KTickUs, TCallBack(TickCallback, this));
    iRunning = ETrue;
    iFinished = EFalse;
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
    iRemainSec = iSetTotalSec;
    iFinished = EFalse;
    UpdateSoftkeys();
    RefreshView();
}

void CPomoAppUi::SetPresetMinutes(TInt aMinutes)
{
    if (iRunning)
        return;
    SetTotalSec(aMinutes * 60);
}

void CPomoAppUi::BeepDone()
{
    User::Beep(880, 200000);
    User::After(250000);
    User::Beep(988, 200000);
    User::After(250000);
    User::Beep(1175, 400000);

    TRAP_IGNORE(
        {
            CAknInformationNote* note = new (ELeave) CAknInformationNote(ETrue);
            note->ExecuteLD(KDoneNote);
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
        iFinished = ETrue;
        UpdateSoftkeys();
        RefreshView();
        BeepDone();
    }
}

void CPomoAppUi::HandleCommandL(TInt aCommand)
{
    switch (aCommand)
    {
    case EAknSoftkeyOk:
    case ECmdStartStop:
        if (iRunning)
            StopTimer();
        else
            StartTimerL();
        break;
    case ECmdMinMinus:
        AdjustMinutes(-1);
        break;
    case ECmdMinPlus:
        AdjustMinutes(1);
        break;
    case ECmdSecMinus:
        AdjustSeconds(-1);
        break;
    case ECmdSecPlus:
        AdjustSeconds(1);
        break;
    case ECmdSet5:
        SetPresetMinutes(5);
        break;
    case ECmdSet15:
        SetPresetMinutes(15);
        break;
    case ECmdSet25:
        SetPresetMinutes(25);
        break;
    case ECmdSet45:
        SetPresetMinutes(45);
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

"use client";

import type { IScannerControls } from "@zxing/browser";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Camera,
  CameraOff,
  CheckCircle2,
  Flashlight,
  RefreshCw,
  ShieldAlert,
  UserCheck,
  XCircle,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import { Button, Input, StatusBadge } from "@/components/ui/primitives";
import { AdminGuardShell } from "@/features/admin/admin-shell";
import { ApiClientError, apiFetch, formatDateTime } from "@/lib/api-client";
import type { CheckInRecord, VerificationResult } from "@/types/api";

function ScannerInner() {
  const queryClient = useQueryClient();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const controlsRef = useRef<IScannerControls | null>(null);
  const lastScannedRef = useRef<{ payload: string; ts: number }>({ payload: "", ts: 0 });
  const scannerLockedRef = useRef(false);

  const [cameraActive, setCameraActive] = useState(false);
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>("");
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [torchSupported, setTorchSupported] = useState(false);
  const [torchOn, setTorchOn] = useState(false);

  const [qrInput, setQrInput] = useState("");
  const [manualRef, setManualRef] = useState("");
  const [confirmManualStaffCheck, setConfirmManualStaffCheck] = useState(false);
  const [notes, setNotes] = useState("");

  const [verifying, setVerifying] = useState(false);
  const [admitting, setAdmitting] = useState(false);
  const [activeQrPayload, setActiveQrPayload] = useState("");
  const [verification, setVerification] = useState<VerificationResult | null>(null);
  const [admittedRecord, setAdmittedRecord] = useState<CheckInRecord | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    scannerLockedRef.current =
      verifying || admitting || verification !== null || admittedRecord !== null;
  }, [verifying, admitting, verification, admittedRecord]);

  const stopCamera = useCallback(() => {
    controlsRef.current?.stop();
    controlsRef.current = null;
    if (videoRef.current?.srcObject instanceof MediaStream) {
      for (const track of videoRef.current.srcObject.getTracks()) {
        track.stop();
      }
      videoRef.current.srcObject = null;
    }
    setCameraActive(false);
    setTorchSupported(false);
    setTorchOn(false);
  }, []);

  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, [stopCamera]);

  const verifyQrCode = useCallback(async (rawPayload: string) => {
    const trimmed = rawPayload.trim();
    if (!trimmed) return;
    setVerifying(true);
    setActionError(null);
    setAdmittedRecord(null);
    setConfirmManualStaffCheck(false);
    setActiveQrPayload(trimmed);

    try {
      const res = await apiFetch<VerificationResult>("/api/verify/", {
        method: "POST",
        json: { qr_payload: trimmed },
      });
      setVerification(res);
    } catch (err) {
      setActionError(err instanceof ApiClientError ? err.message : "Failed to verify QR code.");
    } finally {
      setVerifying(false);
    }
  }, []);

  const startCamera = async (preferredDeviceId?: string) => {
    setCameraError(null);
    stopCamera();

    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setCameraError(
        "Camera access is unavailable in this browser context. Use the QR token or manual reference verification form below.",
      );
      return;
    }

    try {
      const { BrowserQRCodeReader } = await import("@zxing/browser");
      const videoInputs = await BrowserQRCodeReader.listVideoInputDevices();
      setDevices(videoInputs);

      let chosenId = preferredDeviceId || selectedDeviceId;
      if (!chosenId && videoInputs.length > 0) {
        const rear = videoInputs.find((d) => /back|rear|environment/i.test(d.label));
        chosenId = (rear ?? videoInputs[0])!.deviceId;
        setSelectedDeviceId(chosenId);
      }

      const reader = new BrowserQRCodeReader();
      if (!videoRef.current) return;

      const controls = await reader.decodeFromVideoDevice(
        chosenId || undefined,
        videoRef.current,
        (result) => {
          if (!result || scannerLockedRef.current) return;
          const text = result.getText();
          const now = Date.now();
          if (
            text === lastScannedRef.current.payload &&
            now - lastScannedRef.current.ts < 3500
          ) {
            return;
          }
          scannerLockedRef.current = true;
          lastScannedRef.current = { payload: text, ts: now };
          void verifyQrCode(text);
        },
      );

      controlsRef.current = controls;
      setCameraActive(true);

      // Detect optional torch capability
      const stream = videoRef.current.srcObject;
      if (stream instanceof MediaStream) {
        const track = stream.getVideoTracks()[0];
        const caps = track?.getCapabilities?.() as Record<string, unknown> | undefined;
        setTorchSupported(Boolean(caps && "torch" in caps && controls.switchTorch));
      }
    } catch {
      setCameraError(
        "Camera permission was denied or no camera was detected. You can verify guests below using manual reference lookup.",
      );
    }
  };

  const toggleTorch = async () => {
    if (!controlsRef.current?.switchTorch) return;
    try {
      const next = !torchOn;
      await controlsRef.current.switchTorch(next);
      setTorchOn(next);
    } catch {
      setTorchSupported(false);
    }
  };

  const handleQrFormSubmit = async (e: FormEvent) => {
    e.preventDefault();
    await verifyQrCode(qrInput);
  };

  const handleManualVerify = async (e: FormEvent) => {
    e.preventDefault();
    if (!manualRef.trim()) return;
    setVerifying(true);
    setActionError(null);
    setAdmittedRecord(null);
    setConfirmManualStaffCheck(false);
    setActiveQrPayload("");

    try {
      const res = await apiFetch<VerificationResult>("/api/verify/manual/", {
        method: "POST",
        json: { reference: manualRef.trim().toUpperCase() },
      });
      setVerification(res);
    } catch (err) {
      setActionError(err instanceof ApiClientError ? err.message : "Manual verification failed.");
    } finally {
      setVerifying(false);
    }
  };

  const handleAdmitGuest = async () => {
    if (!verification || !verification.can_admit) return;
    setAdmitting(true);
    setActionError(null);

    try {
      const checkin = await apiFetch<CheckInRecord>("/api/check-in/", {
        method: "POST",
        json: {
          verification_method: verification.verification_method,
          qr_payload: verification.verification_method === "QR" ? activeQrPayload : "",
          reference: verification.reference || manualRef.trim().toUpperCase(),
          confirm_manual: verification.verification_method === "MANUAL" ? confirmManualStaffCheck : false,
          notes,
        },
      });
      setAdmittedRecord(checkin);
      setVerification(null);
      setNotes("");
      setQrInput("");
      await queryClient.invalidateQueries({ queryKey: ["admin-dashboard"] });
      await queryClient.invalidateQueries({ queryKey: ["admin-checkins"] });
    } catch (err) {
      setActionError(err instanceof ApiClientError ? err.message : "Admission failed.");
    } finally {
      setAdmitting(false);
    }
  };

  const resetScannerState = () => {
    setVerification(null);
    setAdmittedRecord(null);
    setActionError(null);
    setNotes("");
    lastScannedRef.current = { payload: "", ts: 0 };
  };

  return (
    <div className="space-y-6">
      <div className="border-b border-champagne/15 pb-5">
        <h1 className="font-display text-4xl tracking-wide text-ivory uppercase">
          ENTRANCE QR SCANNER
        </h1>
        <p className="mt-1 text-sm text-ivory-muted">
          Scan official guest QR passes to verify eligibility first, then press Admit Guest to record single entry.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Left: Camera + Input Controls */}
        <div className="space-y-6 lg:col-span-6">
          <section className="rounded-lg border border-champagne/25 bg-espresso p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="font-display text-2xl tracking-wide text-ivory uppercase">
                CAMERA SCANNER
              </h2>
              <div className="flex flex-wrap gap-2">
                {!cameraActive ? (
                  <Button size="sm" onClick={() => void startCamera()}>
                    <Camera className="h-4 w-4" />
                    Start Camera
                  </Button>
                ) : (
                  <>
                    {torchSupported && (
                      <Button variant="outline" size="sm" onClick={() => void toggleTorch()}>
                        <Flashlight className="h-4 w-4" />
                        {torchOn ? "Torch Off" : "Torch On"}
                      </Button>
                    )}
                    <Button variant="secondary" size="sm" onClick={stopCamera}>
                      <CameraOff className="h-4 w-4" />
                      Stop
                    </Button>
                  </>
                )}
              </div>
            </div>

            {devices.length > 1 && cameraActive && (
              <div className="mt-3">
                <label htmlFor="camera-select" className="sr-only">
                  Select camera
                </label>
                <select
                  id="camera-select"
                  value={selectedDeviceId}
                  onChange={(e) => {
                    setSelectedDeviceId(e.target.value);
                    void startCamera(e.target.value);
                  }}
                  className="min-h-11 w-full rounded border border-champagne/25 bg-midnight px-3 text-xs text-ivory"
                >
                  {devices.map((dev, i) => (
                    <option key={dev.deviceId || i} value={dev.deviceId}>
                      {dev.label || `Camera ${i + 1}`}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="relative mt-4 aspect-[4/3] overflow-hidden rounded-md border border-champagne/20 bg-black">
              <video
                ref={videoRef}
                muted
                playsInline
                className="h-full w-full object-cover"
              />
              {!cameraActive && (
                <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center text-xs text-ivory-muted">
                  <Camera className="mb-2 h-8 w-8 text-champagne/50" />
                  <span>Press Start Camera to scan guest PDF QR codes using the rear camera.</span>
                </div>
              )}
            </div>

            {cameraError && (
              <p role="alert" className="mt-3 text-xs text-amber">
                {cameraError}
              </p>
            )}

            {/* Direct QR Payload Paste / Hardware Scanner Input */}
            <form onSubmit={handleQrFormSubmit} className="mt-4 flex gap-2">
              <Input
                aria-label="QR payload input"
                value={qrInput}
                onChange={(e) => setQrInput(e.target.value)}
                placeholder="Or scan/paste QR payload (DRIP1:...)"
                className="font-mono text-xs"
              />
              <Button type="submit" variant="outline" loading={verifying} className="shrink-0">
                Verify QR
              </Button>
            </form>
          </section>

          {/* Manual Invitation Reference Fallback */}
          <section className="rounded-lg border border-champagne/20 bg-espresso p-5">
            <h2 className="font-display text-xl tracking-wide text-ivory uppercase">
              MANUAL REFERENCE FALLBACK
            </h2>
            <p className="mt-1 text-xs text-ivory-muted">
              If a camera cannot read a damaged screen, inspect by invitation reference (e.g. DR-83729164). Requires staff check of the guest&apos;s official PDF pass.
            </p>
            <form onSubmit={handleManualVerify} className="mt-3 flex gap-2">
              <Input
                aria-label="Manual invitation reference"
                value={manualRef}
                onChange={(e) => setManualRef(e.target.value)}
                placeholder="DR-83729164"
                className="uppercase"
              />
              <Button type="submit" variant="secondary" loading={verifying} className="shrink-0">
                Lookup Ref
              </Button>
            </form>
          </section>
        </div>

        {/* Right: Verification & Admission Decision Panel */}
        <div className="lg:col-span-6">
          {actionError && (
            <div
              role="alert"
              className="mb-4 rounded-lg border border-status-err/60 bg-red-950/75 p-4 text-sm text-red-100"
            >
              {actionError}
            </div>
          )}

          {admittedRecord ? (
            <div
              role="status"
              className="rounded-lg border-2 border-emerald-400 bg-emerald-950/80 p-7 text-ivory"
            >
              <div className="flex items-center gap-3">
                <UserCheck className="h-9 w-9 text-emerald-300" />
                <div>
                  <StatusBadge tone="success">ADMISSION RECORDED</StatusBadge>
                  <h2 className="font-display mt-1 text-3xl tracking-wide uppercase">
                    WELCOME {admittedRecord.nickname}
                  </h2>
                </div>
              </div>
              <dl className="mt-5 space-y-2 text-sm">
                <div className="flex justify-between">
                  <dt className="text-emerald-200/80">Reference</dt>
                  <dd className="font-mono font-bold">{admittedRecord.reference}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-emerald-200/80">Checked In At</dt>
                  <dd>{formatDateTime(admittedRecord.checked_in_at)}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-emerald-200/80">Method</dt>
                  <dd>{admittedRecord.verification_method}</dd>
                </div>
              </dl>
              <Button variant="outline" className="mt-6 w-full" onClick={resetScannerState}>
                <RefreshCw className="h-4 w-4" />
                Ready for Next Guest
              </Button>
            </div>
          ) : verification ? (
            <VerificationCard
              verification={verification}
              notes={notes}
              setNotes={setNotes}
              confirmManualStaffCheck={confirmManualStaffCheck}
              setConfirmManualStaffCheck={setConfirmManualStaffCheck}
              admitting={admitting}
              onAdmit={() => void handleAdmitGuest()}
              onClear={resetScannerState}
            />
          ) : (
            <div className="flex min-h-[320px] flex-col items-center justify-center rounded-lg border border-champagne/20 bg-espresso p-8 text-center">
              <p className="font-display text-2xl tracking-wide text-champagne uppercase">
                AWAITING SCAN OR LOOKUP
              </p>
              <p className="mt-2 max-w-sm text-sm text-ivory-muted">
                Scan a guest&apos;s QR code or look up their invitation reference to inspect validity before admitting.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function VerificationCard({
  verification,
  notes,
  setNotes,
  confirmManualStaffCheck,
  setConfirmManualStaffCheck,
  admitting,
  onAdmit,
  onClear,
}: {
  verification: VerificationResult;
  notes: string;
  setNotes: (v: string) => void;
  confirmManualStaffCheck: boolean;
  setConfirmManualStaffCheck: (v: boolean) => void;
  admitting: boolean;
  onAdmit: () => void;
  onClear: () => void;
}) {
  const isValid = verification.result_code === "VALID";
  const isAlreadyAdmitted = verification.result_code === "ALREADY_ADMITTED";

  return (
    <div
      role="region"
      aria-label="Verification result"
      className={`rounded-lg border-2 p-6 ${
        isValid
          ? "border-emerald-400/80 bg-emerald-950/45"
          : isAlreadyAdmitted
            ? "border-amber-400/80 bg-amber-950/45"
            : "border-red-500/80 bg-red-950/50"
      }`}
    >
      <div className="flex items-start gap-3.5">
        {isValid ? (
          <CheckCircle2 className="mt-0.5 h-8 w-8 shrink-0 text-emerald-300" />
        ) : isAlreadyAdmitted ? (
          <AlertTriangle className="mt-0.5 h-8 w-8 shrink-0 text-amber-300" />
        ) : verification.result_code === "INVITATION_REVOKED" ? (
          <ShieldAlert className="mt-0.5 h-8 w-8 shrink-0 text-red-300" />
        ) : (
          <XCircle className="mt-0.5 h-8 w-8 shrink-0 text-red-300" />
        )}
        <div>
          <StatusBadge tone={isValid ? "success" : isAlreadyAdmitted ? "warning" : "danger"}>
            {verification.result_code.replace(/_/g, " ")}
          </StatusBadge>
          <h2 className="font-display mt-2 text-3xl tracking-wide text-ivory uppercase">
            {verification.nickname || verification.reference || "ADMISSION NOT PERMITTED"}
          </h2>
          <p className="mt-1 text-sm text-ivory/90">{verification.message}</p>
        </div>
      </div>

      <dl className="mt-5 space-y-2 border-t border-ivory/15 pt-4 text-sm">
        {verification.reference && (
          <div className="flex justify-between">
            <dt className="text-ivory-muted">Invitation Reference</dt>
            <dd className="font-mono font-bold text-amber">{verification.reference}</dd>
          </div>
        )}
        {verification.guest_email && (
          <div className="flex justify-between">
            <dt className="text-ivory-muted">Guest Email</dt>
            <dd className="text-ivory">{verification.guest_email}</dd>
          </div>
        )}
        {verification.claimed_at && (
          <div className="flex justify-between">
            <dt className="text-ivory-muted">Claimed Date</dt>
            <dd className="text-ivory">{formatDateTime(verification.claimed_at)}</dd>
          </div>
        )}
        {verification.generated_by_name && (
          <div className="flex justify-between">
            <dt className="text-ivory-muted">Host</dt>
            <dd className="text-ivory">{verification.generated_by_name}</dd>
          </div>
        )}
        {verification.checked_in_at && (
          <div className="flex justify-between">
            <dt className="text-ivory-muted">Previous Check-In</dt>
            <dd className="font-semibold text-amber">
              {formatDateTime(verification.checked_in_at)} ({verification.verified_by_name})
            </dd>
          </div>
        )}
      </dl>

      {verification.manual_warning && (
        <div className="mt-4 rounded border border-amber/50 bg-chocolate/80 p-3.5 text-xs text-ivory">
          <p className="font-semibold text-amber">Manual Verification Warning</p>
          <p className="mt-1 leading-relaxed">{verification.manual_warning}</p>
          {isValid && (
            <label className="mt-3 flex cursor-pointer items-center gap-2.5 font-semibold text-ivory">
              <input
                type="checkbox"
                checked={confirmManualStaffCheck}
                onChange={(e) => setConfirmManualStaffCheck(e.target.checked)}
                className="h-4 w-4 accent-burnt"
              />
              <span>I have verified the guest&apos;s presented official PDF invitation</span>
            </label>
          )}
        </div>
      )}

      {isValid && (
        <div className="mt-5 space-y-3">
          <Input
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Optional entrance note..."
            aria-label="Entrance notes"
          />
          <Button
            size="lg"
            loading={admitting}
            disabled={verification.verification_method === "MANUAL" && !confirmManualStaffCheck}
            onClick={onAdmit}
            className="w-full"
          >
            <UserCheck className="h-5 w-5" />
            ADMIT GUEST
          </Button>
        </div>
      )}

      <Button variant="ghost" size="sm" className="mt-3 w-full" onClick={onClear}>
        Clear Result
      </Button>
    </div>
  );
}

export default function AdminScannerPage() {
  return (
    <AdminGuardShell>
      <ScannerInner />
    </AdminGuardShell>
  );
}

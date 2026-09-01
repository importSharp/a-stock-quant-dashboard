"use client";

import { useEffect } from "react";

export function PwaRegister() {
  useEffect(() => {
    if ("serviceWorker" in navigator) {
      let reloading = false;
      const handleControllerChange = () => {
        if (reloading) return;
        reloading = true;
        window.location.reload();
      };
      navigator.serviceWorker.addEventListener("controllerchange", handleControllerChange);
      void navigator.serviceWorker
        .register("/sw.js?v=3", { updateViaCache: "none" })
        .then((registration) => registration.update());
      return () => navigator.serviceWorker.removeEventListener("controllerchange", handleControllerChange);
    }
  }, []);
  return null;
}

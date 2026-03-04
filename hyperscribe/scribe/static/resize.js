import { useEffect } from 'https://esm.sh/preact@10.25.4/hooks';

/**
 * Hook that establishes a MessageChannel with the parent Canvas app
 * and sends RESIZE messages whenever the body size changes.
 */
export function useAutoResize() {
  useEffect(() => {
    let messagePort = null;

    const onMessage = (event) => {
      if (event.data?.type === 'INIT_CHANNEL' && event.ports?.[0]) {
        messagePort = event.ports[0];
        messagePort.start();
        sendResize();
      }
    };

    const sendResize = () => {
      if (!messagePort) return;
      const { scrollWidth, scrollHeight } = document.body;
      messagePort.postMessage({
        type: 'RESIZE',
        width: scrollWidth,
        height: scrollHeight,
      });
    };

    window.addEventListener('message', onMessage);

    const observer = new ResizeObserver(sendResize);
    observer.observe(document.body);

    return () => {
      window.removeEventListener('message', onMessage);
      observer.disconnect();
    };
  }, []);
}

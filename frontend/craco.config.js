const path = require('path');

module.exports = {
  devServer: {
    proxy: {
      '/api': {
        target: 'https://refreshing-acceptance-production.up.railway.app',
        changeOrigin: true,
        secure: false,
      },
    },
  },
  webpack: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
    configure: (webpackConfig, { env, paths }) => {
      console.log('🔧 CRACO Config Running...');
      console.log('   Environment:', env);
      console.log('   NODE_ENV:', process.env.NODE_ENV);
      
      // ✅ FIX: Check environment dengan benar
      const isProduction = env === 'production' || process.env.NODE_ENV === 'production';
      
      if (isProduction) {
        console.log('🔥 PRODUCTION MODE DETECTED');
        console.log('   Removing React Refresh...');
        
        // Remove React Refresh Webpack Plugin
        let removedCount = 0;
        webpackConfig.plugins = (webpackConfig.plugins || []).filter(plugin => {
          const name = plugin.constructor.name;
          const shouldRemove = name === 'ReactRefreshPlugin' || 
                              name === 'ReactRefreshWebpackPlugin';
          if (shouldRemove) {
            console.log(`   ✅ Removed plugin: ${name}`);
            removedCount++;
          }
          return !shouldRemove;
        });
        
        if (removedCount === 0) {
          console.log('   ⚠️  Warning: No React Refresh plugins found (might be okay)');
        }
        
        // Remove react-refresh from babel-loader
        const babelLoaderRule = webpackConfig.module.rules
          .find(rule => rule.oneOf)
          ?.oneOf.find(rule => {
            if (rule.loader && rule.loader.includes('babel-loader')) return true;
            if (rule.use) {
              const babelLoader = Array.isArray(rule.use) 
                ? rule.use.find(u => u.loader && u.loader.includes('babel-loader'))
                : (rule.use.loader && rule.use.loader.includes('babel-loader') ? rule.use : null);
              return !!babelLoader;
            }
            return false;
          });
        
        if (babelLoaderRule) {
          const babelOptions = babelLoaderRule.options || 
                              (babelLoaderRule.use && babelLoaderRule.use[0] && babelLoaderRule.use[0].options);
          
          if (babelOptions && babelOptions.plugins) {
            const before = babelOptions.plugins.length;
            babelOptions.plugins = babelOptions.plugins.filter(plugin => {
              const pluginStr = String(plugin);
              return !pluginStr.includes('react-refresh');
            });
            const after = babelOptions.plugins.length;
            console.log(`   ✅ Removed ${before - after} react-refresh babel plugin(s)`);
          }
        }
        
        console.log('✅ React Refresh removal complete!');
      } else {
        console.log('🚧 DEVELOPMENT MODE - React Refresh enabled');
      }
      
      return webpackConfig;
    },
  },
};